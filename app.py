import os
import uuid
import simplejson as json
from flask import Flask, request, render_template, send_from_directory, jsonify
from werkzeug.utils import secure_filename

# Importar o motor de conversão geográfico e KML
from converter import process_coordinate_conversion, generate_kml_string

from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configurações do Servidor
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # Aumentado para 32 MB para suportar arquivos gigantes

# Garantir que a pasta de uploads existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    """Rota principal que serve a interface do dashboard."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_coordinates():
    """
    Endpoint POST que recebe o arquivo carregado e os parâmetros estendidos de coordenadas,
    executa a conversão e retorna estatísticas, links de download e amostra dos dados.
    """
    # 1. Validar se o arquivo foi enviado
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Nome de arquivo inválido."}), 400
        
    # Salvar o arquivo de forma segura com UUID
    file_id = str(uuid.uuid4())
    original_filename = secure_filename(file.filename)
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{original_filename}")
    file.save(input_path)
    
    # 2. Resgatar Parâmetros Estendidos de Entrada
    source_type = request.form.get('source_type', 'geo')  # geo, gms, utm, local
    source_datum = request.form.get('source_datum', 'SIRGAS_2000')  # SIRGAS_2000, WGS_84, SAD_69, etc.
    
    try:
        source_utm_zone = int(request.form.get('source_utm_zone', 23))
    except ValueError:
        source_utm_zone = 23
    source_utm_hemi = request.form.get('source_utm_hemi', 'S')  # S, N
    
    # Resgatar Parâmetros Estendidos de Saída
    target_type = request.form.get('target_type', 'UTM_AUTO')  # geo, gms, utm, UTM_AUTO, MGRS, local
    target_datum = request.form.get('target_datum', 'SIRGAS_2000')
    
    try:
        target_utm_zone = int(request.form.get('target_utm_zone', 23))
    except ValueError:
        target_utm_zone = 23
    target_utm_hemi = request.form.get('target_utm_hemi', 'S')
    
    # Parâmetros de Topografia Local (Coordenada Local)
    try:
        local_origin_x = float(request.form.get('local_origin_x', 0.0))
        local_origin_y = float(request.form.get('local_origin_y', 0.0))
        local_origin_zone = int(request.form.get('local_origin_zone', 23))
        local_rotation = float(request.form.get('local_rotation', 0.0))
    except ValueError:
        return jsonify({"success": False, "message": "Parâmetros de topografia local inválidos."}), 400
        
    # 3. Executar o Processamento da Conversão Estendida
    res = process_coordinate_conversion(
        file_path=input_path,
        source_type=source_type,
        source_datum=source_datum,
        source_utm_zone=source_utm_zone,
        source_utm_hemi=source_utm_hemi,
        target_type=target_type,
        target_datum=target_datum,
        target_utm_zone=target_utm_zone,
        target_utm_hemi=target_utm_hemi,
        local_origin_x=local_origin_x,
        local_origin_y=local_origin_y,
        local_origin_zone=local_origin_zone,
        local_rotation=local_rotation
    )
    
    # Limpar arquivo temporário de entrada
    try:
        if os.path.exists(input_path):
            os.remove(input_path)
    except Exception as e:
        print(f"Erro ao remover arquivo temporário de entrada: {e}")
        
    if not res['success']:
        return jsonify(res), 400
        
    df_result = res['df_result']
    col_map = res['stats']['columns']
    total_points = res['total_points']
    
    # 4. Gerar Arquivos de Saída (CSV e KML)
    # 4.1 Exportar CSV de saída
    output_csv_filename = f"converted_{file_id}.csv"
    output_csv_path = os.path.join(app.config['UPLOAD_FOLDER'], output_csv_filename)
    df_result.to_csv(output_csv_path, sep=';', index=False, encoding='utf-8-sig')
    
    # 4.2 Exportar KML de saída
    output_kml_filename = f"converted_{file_id}.kml"
    output_kml_path = os.path.join(app.config['UPLOAD_FOLDER'], output_kml_filename)
    
    if source_type == 'local':
        local_params = {
            'origin_x': local_origin_x,
            'origin_y': local_origin_y,
            'zone': local_origin_zone,
            'rotation': local_rotation
        }
    else:
        local_params = None
        
    kml_string = generate_kml_string(
        df=df_result,
        col_id=col_map['id'],
        col_x=col_map['x'],
        col_y=col_map['y'],
        col_z=col_map['z'],
        source_type=source_type,
        source_datum=source_datum,
        source_utm_zone=source_utm_zone,
        source_utm_hemi=source_utm_hemi,
        local_params=local_params
    )
    
    with open(output_kml_path, 'w', encoding='utf-8') as kf:
        kf.write(kml_string)
        
    # 5. Filtrar os primeiros 100 pontos para renderizar no Mapa e Tabela
    # Como as coordenadas geográficas de visualização MAP_LON e MAP_LAT já são calculadas
    # perfeitamente no motor (converter.py) para todos os pontos, filtramos diretamente!
    df_sample = df_result.head(100).copy()
    
    # 6. Serializar usando simplejson para não perder precisão decimal dos pontos
    points_list = df_sample.to_dict(orient='records')
    
    # Calcular contagem de alertas de precisão em todo o dataset
    alert_count = int(df_result['PRECISION_ALERT'].sum())
    has_alerts = bool(alert_count > 0)
    
    response_data = {
        "success": True,
        "message": "Conversão concluída com sucesso.",
        "total_points": total_points,
        "ignored_points": res['ignored_points'],
        "stats": res['stats'],
        "has_precision_alerts": has_alerts,
        "alert_count": alert_count,
        "download_csv_url": f"/download/{output_csv_filename}",
        "download_kml_url": f"/download/{output_kml_filename}",
        "points": points_list
    }
    
    # Usar simplejson.dumps para preservar floats de forma ultra-precisa
    json_response_str = json.dumps(response_data, ignore_nan=True)
    
    return Flask.response_class(
        response=json_response_str,
        status=200,
        mimetype='application/json'
    )

@app.route('/convert_point', methods=['POST', 'GET'])
def convert_point():
    """
    Converte um ponto clicado no mapa (lat, lon em WGS84) para UTM SIRGAS 2000 (Hemisfério Sul)
    e retorna o fuso e as coordenadas em metros.
    """
    import re
    try:
        lat = float(request.args.get('lat') or request.form.get('lat'))
        lon = float(request.args.get('lon') or request.form.get('lon'))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Latitude e Longitude invalidas."}), 400
        
    # Calcular a zona UTM dinamicamente
    from converter import calculate_utm_zone_and_epsg
    zone_str, epsg = calculate_utm_zone_and_epsg(lon, lat, datum='SIRGAS_2000')
    zone_num = int(re.findall(r'\d+', zone_str)[0])
    
    # Converter de WGS 84 (EPSG:4326) para a UTM SIRGAS 2000 correspondente
    from pyproj import Transformer
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    x, y = to_utm.transform(lon, lat)
    
    return jsonify({
        "success": True,
        "x": round(x, 3),
        "y": round(y, 3),
        "zone": zone_num
    })

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Rota para baixar os arquivos CSV ou KML gerados."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
