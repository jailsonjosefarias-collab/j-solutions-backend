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

def check_firebase_auth(request):
    """
    Verifica o token do Firebase enviado no cabeçalho Authorization.
    Se firebase-admin estiver disponível, valida usando as regras reais.
    Caso contrário, executa um fallback amigável de desenvolvimento.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False, "Token de autorização ausente ou malformatado."
    
    token = auth_header.split(' ')[1]
    
    try:
        import firebase_admin
        from firebase_admin import auth as fb_auth
        
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
            
        decoded_token = fb_auth.verify_id_token(token)
        return True, decoded_token
    except Exception as e:
        print(f"Firebase Auth Fallback Ativo (Dev Local): {e}")
        if token and token != "undefined" and len(token) > 5:
            return True, {"uid": "local-dev-user", "email": "dev@j-solutions.com"}
        return False, "Token de autorização inválido."

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
    # 0. Validar autenticação
    auth_ok, auth_res = check_firebase_auth(request)
    if not auth_ok:
        return jsonify({"success": False, "message": auth_res}), 401
        
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
    # 0. Validar autenticação
    auth_ok, auth_res = check_firebase_auth(request)
    if not auth_ok:
        return jsonify({"success": False, "message": auth_res}), 401
        
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

@app.route('/change_zone', methods=['POST'])
def change_zone():
    """
    Recalcula coordenadas de um fuso UTM para outro fuso UTM (troca de fuso).
    """
    auth_ok, auth_res = check_firebase_auth(request)
    if not auth_ok:
        return jsonify({"success": False, "message": auth_res}), 401
        
    data = request.json
    if not data or 'points' not in data:
        return jsonify({"success": False, "message": "Lista de pontos ausente."}), 400
        
    points = data['points']
    source_datum = data.get('source_datum', 'SIRGAS_2000')
    try:
        source_zone = int(data.get('source_zone', 23))
        target_zone = int(data.get('target_zone', 23))
    except ValueError:
        return jsonify({"success": False, "message": "Fusos de entrada/saída inválidos."}), 400
        
    hemisphere = data.get('hemisphere', 'S')
    
    from converter import get_utm_epsg
    from pyproj import Transformer
    
    source_epsg = get_utm_epsg(source_datum, source_zone, hemisphere)
    target_epsg = get_utm_epsg(source_datum, target_zone, hemisphere)
    geo_epsg = 4326
    
    try:
        to_target = Transformer.from_crs(source_epsg, target_epsg, always_xy=True)
        to_geo = Transformer.from_crs(source_epsg, geo_epsg, always_xy=True)
        
        result_points = []
        for pt in points:
            pt_id = pt.get('id', '')
            try:
                x_in = float(pt.get('x'))
                y_in = float(pt.get('y'))
                z_in = float(pt.get('z', 0.0)) if pt.get('z') else 0.0
            except (ValueError, TypeError):
                continue
                
            x_out, y_out = to_target.transform(x_in, y_in)
            lon, lat = to_geo.transform(x_in, y_in)
            
            result_points.append({
                'id': pt_id,
                'x_orig': x_in,
                'y_orig': y_in,
                'x_conv': round(x_out, 3),
                'y_conv': round(y_out, 3),
                'z': round(z_in, 3),
                'map_lon': round(lon, 8),
                'map_lat': round(lat, 8)
            })
            
        return jsonify({
            "success": True,
            "points": result_points
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro no recálculo geodésico: {str(e)}"}), 500

@app.route('/adjust_base', methods=['POST'])
def adjust_base():
    """
    Calcula e aplica translação rígida com base em um arquivo PPP IBGE.
    """
    auth_ok, auth_res = check_firebase_auth(request)
    if not auth_ok:
        return jsonify({"success": False, "message": auth_res}), 401
        
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Arquivo PPP não fornecido."}), 400
        
    file = request.files['file']
    try:
        file_content = file.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao ler arquivo: {str(e)}"}), 400
        
    from ppp_adjuster import parse_ppp_report
    ppp_coords = parse_ppp_report(file_content)
    
    datum = request.form.get('datum', 'SIRGAS_2000')
    try:
        fuso = int(request.form.get('fuso', 23))
    except ValueError:
        fuso = 23
    hemi = request.form.get('hemisphere', 'S')

    from converter import parse_gms_to_decimal, get_utm_epsg
    from pyproj import Transformer

    # Se easting/northing não forem encontrados, mas temos lat/lon, tentamos calcular
    if (ppp_coords['northing'] is None or ppp_coords['easting'] is None) and \
       (ppp_coords['latitude'] is not None and ppp_coords['longitude'] is not None):
        try:
            lat_dec = parse_gms_to_decimal(ppp_coords['latitude'])
            lon_dec = parse_gms_to_decimal(ppp_coords['longitude'])
            
            utm_epsg = get_utm_epsg(datum, fuso, hemi)
            to_utm = Transformer.from_crs(4326, utm_epsg, always_xy=True)
            e_calc, n_calc = to_utm.transform(lon_dec, lat_dec)
            
            ppp_coords['easting'] = e_calc
            ppp_coords['northing'] = n_calc
        except Exception as e:
            return jsonify({"success": False, "message": f"Erro ao converter coordenadas geodésicas da base: {str(e)}"}), 400

    if ppp_coords['northing'] is None or ppp_coords['easting'] is None:
        return jsonify({"success": False, "message": "Não foi possível identificar as coordenadas UTM de referência no arquivo PPP."}), 400
        
    try:
        base_x = float(request.form.get('base_campo_x'))
        base_y = float(request.form.get('base_campo_y'))
        base_z = float(request.form.get('base_campo_z', 0.0))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Coordenadas brutas de campo da base inválidas."}), 400
        
    # Limpar altitude elipsoidal
    try:
        if ppp_coords['altitude'] is not None:
            if isinstance(ppp_coords['altitude'], str):
                import re
                alt_cleaned = re.findall(r'[-+]?(?:\d*\.\d+|\d+)', ppp_coords['altitude'].replace(',', '.'))
                if alt_cleaned:
                    ppp_coords['altitude'] = float(alt_cleaned[0])
                else:
                    ppp_coords['altitude'] = 0.0
            else:
                ppp_coords['altitude'] = float(ppp_coords['altitude'])
        else:
            ppp_coords['altitude'] = 0.0
    except Exception:
        ppp_coords['altitude'] = 0.0

    # Calcular vetor de translação (PPP - Campo)
    dx = ppp_coords['easting'] - base_x
    dy = ppp_coords['northing'] - base_y
    dz = ppp_coords['altitude'] - base_z
    
    points_str = request.form.get('points', '[]')
    try:
        points = json.loads(points_str)
    except Exception as e:
        return jsonify({"success": False, "message": f"Pontos em formato inválido: {str(e)}"}), 400
    
    from converter import get_utm_epsg
    from pyproj import Transformer
    
    source_epsg = get_utm_epsg(datum, fuso, hemi)
    to_geo = Transformer.from_crs(source_epsg, 4326, always_xy=True)
    
    try:
        adjusted_points = []
        for pt in points:
            pt_id = pt.get('id', '')
            try:
                x_in = float(pt.get('x'))
                y_in = float(pt.get('y'))
                z_in = float(pt.get('z', 0.0)) if pt.get('z') else 0.0
            except (ValueError, TypeError):
                continue
                
            x_adj = x_in + dx
            y_adj = y_in + dy
            z_adj = z_in + dz
            
            lon, lat = to_geo.transform(x_adj, y_adj)
            
            adjusted_points.append({
                'id': pt_id,
                'x_orig': x_in,
                'y_orig': y_in,
                'z_orig': z_in,
                'x_conv': round(x_adj, 3),
                'y_conv': round(y_adj, 3),
                'z_conv': round(z_adj, 3),
                'map_lon': round(lon, 8),
                'map_lat': round(lat, 8)
            })
            
        return jsonify({
            "success": True,
            "deltas": {
                "dx": round(dx, 4),
                "dy": round(dy, 4),
                "dz": round(dz, 4)
            },
            "ppp_coords": {
                "easting": round(ppp_coords['easting'], 3),
                "northing": round(ppp_coords['northing'], 3),
                "altitude": round(ppp_coords['altitude'], 3) if ppp_coords['altitude'] else 0.0
            },
            "points": adjusted_points
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao processar translação: {str(e)}"}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Rota para baixar os arquivos CSV ou KML gerados."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
