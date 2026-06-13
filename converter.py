import os
import math
import re
import pandas as pd
import numpy as np
from pyproj import CRS, Transformer

# Tentar importar mgrs para suporte a MGRS. Caso não esteja instalado, definimos uma flag de fallback.
try:
    import mgrs
    MGRS_AVAILABLE = True
except ImportError:
    MGRS_AVAILABLE = False

def detect_delimiter(file_path):
    """
    Detecta automaticamente se o delimitador do arquivo é vírgula (,), ponto e vírgula (;) ou tabulação (\t).
    Lê as primeiras 10 linhas do arquivo para análise estatística.
    """
    delimiters = [',', ';', '\t']
    counts = {d: 0 for d in delimiters}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(10)]
            
        # Contar ocorrências nas linhas lidas
        for line in lines:
            if not line.strip():
                continue
            for d in delimiters:
                counts[d] += line.count(d)
                
        # Seleciona o delimitador com maior contagem
        best_delim = max(counts, key=counts.get)
        # Se nenhum delimitador foi encontrado de forma expressiva, assume vírgula como padrão
        if counts[best_delim] == 0:
            return ','
        return best_delim
    except Exception as e:
        print(f"Erro ao detectar delimitador: {e}")
        return ','

def parse_gms_to_decimal(val):
    """
    Analisa de forma ultra robusta strings em formato GMS (Graus, Minutos e Segundos)
    ou Decimais e converte para Graus Decimais (float), aplicando sinal negativo (-)
    automaticamente por estarmos no Hemisfério Sul/Oeste, exceto se houver indicação
    positiva explícita (+ ou N, NORTE, E, EAST, L, LESTE).
    """
    if pd.isna(val) or val is None:
        return np.nan
        
    val_str = str(val).strip()
    if not val_str:
        return np.nan
        
    # Substituir vírgula decimal por ponto na parte dos segundos para evitar conflito com espaço
    val_str = re.sub(r'(\d+),(\d+)', r'\1.\2', val_str)
    
    # Extrair todos os números (inteiros ou decimais com sinais opcionais)
    numbers = re.findall(r'[-+]?(?:\d*\.\d+|\d+)', val_str)
    
    if not numbers:
        return np.nan
        
    # Atribuir Graus, Minutos e Segundos
    try:
        d = float(numbers[0])
        m = float(numbers[1]) if len(numbers) > 1 else 0.0
        s = float(numbers[2]) if len(numbers) > 2 else 0.0
    except Exception:
        return np.nan
        
    decimal = abs(d) + (m / 60.0) + (s / 3600.0)
    
    # Verificar hemisférios ou indicação explícita positiva
    val_upper = val_str.upper()
    has_explicit_positive = (val_str.startswith('+') or 
                             any(h in val_upper for h in ['N', 'NORTE', 'E', 'EAST', 'L', 'LESTE']))
    
    is_negative = True # Padrão: Hemisfério Sul/Oeste
    if has_explicit_positive:
        is_negative = False
    elif d < 0 or '-' in numbers[0]:
        is_negative = True
        
    if is_negative:
        decimal = -decimal
        
    return decimal

def decimal_to_gms(decimal, is_lat=True):
    """
    Converte uma coordenada em Graus Decimais para uma string GMS elegante e padronizada.
    Exemplo: -23.5505 -> 23° 33' 01.8000" S
    """
    if pd.isna(decimal) or decimal is None:
        return ""
        
    try:
        val = float(decimal)
    except (ValueError, TypeError):
        return str(decimal)
        
    abs_val = abs(val)
    d = int(math.floor(abs_val))
    m = int(math.floor((abs_val - d) * 60))
    s = ((abs_val - d) * 60 - m) * 60
    
    # Tratar arredondamentos limite
    if round(s, 4) >= 60.0:
        s = 0.0
        m += 1
        if m >= 60:
            m = 0
            d += 1
            
    # Hemisférios
    if is_lat:
        hemi = 'S' if val < 0 else 'N'
    else:
        hemi = 'W' if val < 0 else 'E'
        
    return f"{d}° {m:02d}' {s:07.4f}\" {hemi}"

def calculate_utm_zone_and_epsg(lon, lat, datum='SIRGAS_2000'):
    """
    Calcula dinamicamente a zona UTM com base na longitude.
    Retorna a zona (ex: '23S') e o código EPSG correspondente para o Datum selecionado.
    """
    lon = max(-180.0, min(180.0, float(lon)))
    lat = float(lat)
    
    zone = int(math.floor((lon + 180) / 6)) + 1
    zone = max(1, min(60, zone))
    hemi = 'N' if lat >= 0 else 'S'
    
    epsg = get_utm_epsg(datum, zone, hemi)
    return f"{zone}{hemi}", epsg

def get_utm_epsg(datum, zone, hemisphere):
    """
    Retorna o código EPSG da projeção UTM oficial com base no Datum, Fuso e Hemisfério.
    """
    zone = int(zone)
    hemi = str(hemisphere).upper().strip()
    
    if datum == 'SIRGAS_2000':
        # SIRGAS 2000 / UTM
        return (31900 + zone) if hemi == 'N' else (31960 + zone)
        
    elif datum == 'WGS_84':
        # WGS 84 / UTM
        return (32600 + zone) if hemi == 'N' else (32700 + zone)
        
    elif datum == 'SAD_69':
        # SAD 69 / UTM - Oficialmente usado no Brasil principalmente para o Hemisfério Sul (Zonas 18 a 25)
        # SAD69(96) ou SAD69 tradicional geográficas EPSG:4618
        if hemi == 'S' and 18 <= zone <= 25:
            # Mapeamento oficial de zonas do Brasil SAD69 UTM Sul (EPSG 29188 a 29195)
            return 29170 + zone
        # Fallback genérico para SAD69 UTM se for outra zona
        return (29100 + zone) if hemi == 'N' else (29160 + zone)
        
    elif datum == 'CORREGO_ALEGRE':
        # Córrego Alegre / UTM (Zonas 22, 23, 24 Sul)
        if hemi == 'S' and 22 <= zone <= 24:
            return 22500 + zone
        # Fallback padrão
        return 22500 + zone
        
    elif datum == 'ARATU':
        # Aratu / UTM (Zonas 22, 23, 24 Sul)
        if hemi == 'S' and 22 <= zone <= 24:
            return 31970 + zone
        return 31970 + zone
        
    # Fallback global para SIRGAS 2000 UTM
    return (31960 + zone)

def get_geographic_epsg(datum):
    """Retorna o código EPSG Geográfico correspondente ao Datum."""
    mapping = {
        'SIRGAS_2000': 4674,
        'WGS_84': 4326,
        'SAD_69': 4618,
        'CORREGO_ALEGRE': 4225,
        'ARATU': 4624
    }
    return mapping.get(datum, 4674)

def map_columns(df):
    """
    Mapeia colunas do dataframe para identificar: ID/Nome, X (E/Lon), Y (N/Lat), Z (Alt).
    """
    columns = [col.lower().strip() for col in df.columns]
    col_mapping = {}
    
    patterns = {
        'id': [r'^id$', r'^name$', r'^nome$', r'^ponto$', r'^pt$', r'^cod$', r'^codigo$'],
        'x': [r'^x$', r'^east$', r'^easting$', r'^leste$', r'^e$', r'^long$', r'^longitude$', r'^lon$', r'^lng$'],
        'y': [r'^y$', r'^north$', r'^northing$', r'^norte$', r'^n$', r'^lat$', r'^latitude$'],
        'z': [r'^z$', r'^h$', r'^cota$', r'^elevacao$', r'^elevation$', r'^alt$', r'^altitude$', r'^z_coord$']
    }
    
    for key, regexes in patterns.items():
        found = False
        for regex in regexes:
            for i, col in enumerate(columns):
                if re.match(regex, col):
                    col_mapping[key] = df.columns[i]
                    found = True
                    break
            if found:
                break
        if not found:
            col_mapping[key] = None
            
    return col_mapping

def transform_local_to_utm(x_local, y_local, origin_x, origin_y, rotation_deg=0.0):
    """Realiza a translação e rotação de coordenadas locais para UTM."""
    theta = math.radians(rotation_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    x_rot = x_local * cos_t - y_local * sin_t
    y_rot = x_local * sin_t + y_local * cos_t
    
    x_utm = x_rot + origin_x
    y_utm = y_rot + origin_y
    return x_utm, y_utm

def transform_utm_to_local(x_utm, y_utm, origin_x, origin_y, rotation_deg=0.0):
    """Realiza a transformação inversa de UTM para coordenadas locais."""
    dx = x_utm - origin_x
    dy = y_utm - origin_y
    
    theta = math.radians(-rotation_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    
    x_local = dx * cos_t - dy * sin_t
    y_local = dx * sin_t + dy * cos_t
    return x_local, y_local

def process_coordinate_conversion(
    file_path, 
    source_type, 
    source_datum, 
    source_utm_zone=23, 
    source_utm_hemi='S',
    target_type='UTM_AUTO', 
    target_datum='SIRGAS_2000',
    target_utm_zone=23, 
    target_utm_hemi='S',
    local_origin_x=0.0, 
    local_origin_y=0.0, 
    local_origin_zone=23, 
    local_rotation=0.0
):
    """
    Função principal de processamento em lote robusta e estendida.
    """
    import time
    start_time = time.time()
    
    delim = detect_delimiter(file_path)
    
    try:
        df = pd.read_csv(file_path, sep=delim, decimal='.', encoding='utf-8', errors='ignore')
    except Exception:
        try:
            df = pd.read_csv(file_path, sep=delim, decimal=',', encoding='latin1')
        except Exception as e_inner:
            return {"success": False, "message": f"Erro ao ler arquivo: {str(e_inner)}"}
            
    if df.empty:
        return {"success": False, "message": "O arquivo enviado está vazio."}
        
    df.columns = [c.strip() for c in df.columns]
    col_map = map_columns(df)
    
    if not col_map['x'] or not col_map['y']:
        return {
            "success": False, 
            "message": f"Não foi possível mapear X (Leste/Long) e Y (Norte/Lat). Colunas encontradas: {list(df.columns)}"
        }
        
    col_id = col_map['id']
    col_x = col_map['x']
    col_y = col_map['y']
    col_z = col_map['z']
    
    if not col_id:
        df['PONTO_ID'] = range(1, len(df) + 1)
        col_id = 'PONTO_ID'
        
    # Limpar as colunas X e Y
    # Se a entrada for GMS (Graus Minutos Segundos), aplicamos o parser inteligente
    if source_type in ['gms', 'geo']:
        df[col_x] = df[col_x].apply(parse_gms_to_decimal)
        df[col_y] = df[col_y].apply(parse_gms_to_decimal)
    else:
        df[col_x] = pd.to_numeric(df[col_x].astype(str).str.replace(',', '.'), errors='coerce')
        df[col_y] = pd.to_numeric(df[col_y].astype(str).str.replace(',', '.'), errors='coerce')
        
    if col_z:
        df[col_z] = pd.to_numeric(df[col_z].astype(str).str.replace(',', '.'), errors='coerce')
    else:
        df['COTA_Z'] = 0.0
        col_z = 'COTA_Z'
        
    original_len = len(df)
    df = df.dropna(subset=[col_x, col_y]).copy()
    if len(df) == 0:
        return {"success": False, "message": "Nenhuma linha com coordenadas numéricas/GMS válidas foi encontrada."}
        
    # Determinar EPSG de entrada
    is_source_local = (source_type == 'local')
    is_target_local = (target_type == 'local')
    
    local_epsg = 31960 + int(local_origin_zone)
    
    if is_source_local:
        real_epsg_in = local_epsg
    elif source_type == 'utm':
        real_epsg_in = get_utm_epsg(source_datum, source_utm_zone, source_utm_hemi)
    else:
        # Geográfica decimal ou GMS (que já virou decimal aqui)
        real_epsg_in = get_geographic_epsg(source_datum)
        
    # Determinar EPSG de saída
    is_target_utm_auto = (target_type == 'UTM_AUTO')
    is_target_mgrs = (target_type == 'MGRS')
    
    # Preparar DataFrame de resultados
    df_out = df.copy()
    
    xs_in = df[col_x].to_numpy()
    ys_in = df[col_y].to_numpy()
    
    xs_transformed = np.zeros(len(df))
    ys_transformed = np.zeros(len(df))
    zones_out = []
    
    # Se a entrada for local, fazemos translação e rotação rígida para UTM Real
    if is_source_local:
        v_transform = np.vectorize(transform_local_to_utm)
        xs_temp_in, ys_temp_in = v_transform(
            xs_in, ys_in, 
            origin_x=local_origin_x, 
            origin_y=local_origin_y, 
            rotation_deg=local_rotation
        )
    else:
        xs_temp_in = xs_in
        ys_temp_in = ys_in
        
    # Casos de Transformação
    if is_target_utm_auto or is_target_mgrs:
        # UTM Automático: Calcula zonas baseado em Longitude
        if real_epsg_in == 4674 or real_epsg_in == 4326 or source_type == 'geo' or source_type == 'gms':
            # Se for geográfica
            lons = xs_temp_in
            lats = ys_temp_in
        else:
            # Se for projetada, converte temporariamente para WGS 84 Geográficas para extrair lat/lon
            temp_trans = Transformer.from_crs(real_epsg_in, 4326, always_xy=True)
            lons, lats = temp_trans.transform(xs_temp_in, ys_temp_in)
            
        df_temp = pd.DataFrame({'lon': lons, 'lat': lats, 'idx': np.arange(len(df))})
        v_calc_zone = np.vectorize(calculate_utm_zone_and_epsg)
        zones_str, epsgs_target = v_calc_zone(df_temp['lon'].to_numpy(), df_temp['lat'].to_numpy(), datum=target_datum)
        
        df_temp['zone_str'] = zones_str
        df_temp['epsg_target'] = epsgs_target
        
        if is_target_utm_auto:
            for target_epsg_grp, grp in df_temp.groupby('epsg_target'):
                idx_grp = grp['idx'].to_numpy()
                trans_grp = Transformer.from_crs(real_epsg_in, int(target_epsg_grp), always_xy=True)
                xs_t_grp, ys_t_grp = trans_grp.transform(xs_temp_in[idx_grp], ys_temp_in[idx_grp])
                xs_transformed[idx_grp] = xs_t_grp
                ys_transformed[idx_grp] = ys_t_grp
            zones_out = df_temp['zone_str'].tolist()
            
        elif is_target_mgrs:
            # MGRS necessita de WGS84 Geográficas
            if real_epsg_in != 4326:
                to_wgs84 = Transformer.from_crs(real_epsg_in, 4326, always_xy=True)
                lons_wgs84, lats_wgs84 = to_wgs84.transform(xs_temp_in, ys_temp_in)
            else:
                lons_wgs84 = xs_temp_in
                lats_wgs84 = ys_temp_in
                
            mgrs_strings = []
            if MGRS_AVAILABLE:
                m = mgrs.MGRS()
                for lo, la in zip(lons_wgs84, lats_wgs84):
                    try:
                        mgrs_str = m.toMGRS(la, lo)
                        mgrs_strings.append(mgrs_str.decode('utf-8') if isinstance(mgrs_str, bytes) else mgrs_str)
                    except Exception:
                        mgrs_strings.append("INVALID_MGRS")
            else:
                for lo, la in zip(lons_wgs84, lats_wgs84):
                    z_str, _ = calculate_utm_zone_and_epsg(lo, la, 'WGS_84')
                    mgrs_strings.append(f"{z_str} MGRS_LIB_REQ")
            df_out['CONVERTED_MGRS'] = mgrs_strings
            xs_transformed = lons_wgs84
            ys_transformed = lats_wgs84
            
    elif is_target_local:
        # Alvo é Topografia Local
        trans_to_local_utm = Transformer.from_crs(real_epsg_in, local_epsg, always_xy=True)
        xs_utm_target, ys_utm_target = trans_to_local_utm.transform(xs_temp_in, ys_temp_in)
        
        v_inverse_transform = np.vectorize(transform_utm_to_local)
        xs_transformed, ys_transformed = v_inverse_transform(
            xs_utm_target, ys_utm_target,
            origin_x=local_origin_x,
            origin_y=local_origin_y,
            rotation_deg=local_rotation
        )
        
    else:
        # Destino é padrão (UTM explícita ou Geográfica)
        if target_type == 'utm':
            real_epsg_out = get_utm_epsg(target_datum, target_utm_zone, target_utm_hemi)
        else:
            real_epsg_out = get_geographic_epsg(target_datum)
            
        transformer = Transformer.from_crs(real_epsg_in, real_epsg_out, always_xy=True)
        xs_transformed, ys_transformed = transformer.transform(xs_temp_in, ys_temp_in)
        
    # --- Regra de Precisão de 1cm (Inversa) ---
    xs_recalculated = np.zeros(len(df))
    ys_recalculated = np.zeros(len(df))
    precision_deviations = np.zeros(len(df))
    precision_alerts = np.zeros(len(df), dtype=bool)
    
    if is_target_local:
        v_transform = np.vectorize(transform_local_to_utm)
        xs_recalc_utm, ys_recalc_utm = v_transform(
            xs_transformed, ys_transformed, 
            origin_x=local_origin_x, 
            origin_y=local_origin_y, 
            rotation_deg=local_rotation
        )
        trans_recalc = Transformer.from_crs(local_epsg, real_epsg_in, always_xy=True)
        xs_recalculated, ys_recalculated = trans_recalc.transform(xs_recalc_utm, ys_recalc_utm)
        
    elif is_source_local:
        if is_target_utm_auto:
            for target_epsg_grp, grp in df_temp.groupby('epsg_target'):
                idx_grp = grp['idx'].to_numpy()
                trans_inv = Transformer.from_crs(int(target_epsg_grp), local_epsg, always_xy=True)
                xs_utm_grp, ys_utm_grp = trans_inv.transform(xs_transformed[idx_grp], ys_transformed[idx_grp])
                xs_recalculated[idx_grp], ys_recalculated[idx_grp] = np.vectorize(transform_utm_to_local)(
                    xs_utm_grp, ys_utm_grp,
                    origin_x=local_origin_x, origin_y=local_origin_y, rotation_deg=local_rotation
                )
        elif is_target_mgrs:
            trans_inv = Transformer.from_crs(4326, local_epsg, always_xy=True)
            xs_utm_grp, ys_utm_grp = trans_inv.transform(xs_transformed, ys_transformed)
            xs_recalculated, ys_recalculated = np.vectorize(transform_utm_to_local)(
                xs_utm_grp, ys_utm_grp,
                origin_x=local_origin_x, origin_y=local_origin_y, rotation_deg=local_rotation
            )
        else:
            epsg_out = get_utm_epsg(target_datum, target_utm_zone, target_utm_hemi) if target_type == 'utm' else get_geographic_epsg(target_datum)
            trans_inv = Transformer.from_crs(epsg_out, local_epsg, always_xy=True)
            xs_utm_grp, ys_utm_grp = trans_inv.transform(xs_transformed, ys_transformed)
            xs_recalculated, ys_recalculated = np.vectorize(transform_utm_to_local)(
                xs_utm_grp, ys_utm_grp,
                origin_x=local_origin_x, origin_y=local_origin_y, rotation_deg=local_rotation
            )
    else:
        if is_target_utm_auto:
            for target_epsg_grp, grp in df_temp.groupby('epsg_target'):
                idx_grp = grp['idx'].to_numpy()
                trans_inv = Transformer.from_crs(int(target_epsg_grp), real_epsg_in, always_xy=True)
                xs_recalculated[idx_grp], ys_recalculated[idx_grp] = trans_inv.transform(
                    xs_transformed[idx_grp], ys_transformed[idx_grp]
                )
        elif is_target_mgrs:
            trans_inv = Transformer.from_crs(4326, real_epsg_in, always_xy=True)
            xs_recalculated, ys_recalculated = trans_inv.transform(xs_transformed, ys_transformed)
        else:
            epsg_out = get_utm_epsg(target_datum, target_utm_zone, target_utm_hemi) if target_type == 'utm' else get_geographic_epsg(target_datum)
            trans_inv = Transformer.from_crs(epsg_out, real_epsg_in, always_xy=True)
            xs_recalculated, ys_recalculated = trans_inv.transform(xs_transformed, ys_transformed)

    # Medir distância analítica em metros
    is_source_geo = (real_epsg_in in [4674, 4326, 4618, 4225, 4624])
    
    if is_source_geo:
        # Se a entrada original for geográfica, converte para UTM para calcular a precisão em metros
        v_calc_zone = np.vectorize(calculate_utm_zone_and_epsg)
        _, epsgs_utm_recalc = v_calc_zone(xs_in, ys_in, datum=source_datum)
        
        df_recalc_temp = pd.DataFrame({
            'x_in': xs_in, 'y_in': ys_in,
            'x_rec': xs_recalculated, 'y_rec': ys_recalculated,
            'epsg_utm': epsgs_utm_recalc,
            'idx': np.arange(len(df))
        })
        
        for epsg_utm_grp, grp in df_recalc_temp.groupby('epsg_utm'):
            idx_grp = grp['idx'].to_numpy()
            trans_to_m = Transformer.from_crs(real_epsg_in, int(epsg_utm_grp), always_xy=True)
            xm_in, ym_in = trans_to_m.transform(xs_in[idx_grp], ys_in[idx_grp])
            xm_rec, ym_rec = trans_to_m.transform(xs_recalculated[idx_grp], ys_recalculated[idx_grp])
            devs = np.sqrt((xm_rec - xm_in)**2 + (ym_rec - ym_in)**2)
            precision_deviations[idx_grp] = devs
    else:
        precision_deviations = np.sqrt((xs_recalculated - xs_in)**2 + (ys_recalculated - ys_in)**2)
        
    precision_alerts = precision_deviations > 0.02 # Flag visual: > 2cm
    
    # 7. Salvar Resultados no DataFrame final
    df_out['CONVERTED_X'] = xs_transformed
    df_out['CONVERTED_Y'] = ys_transformed
    df_out['PRECISION_DEV_M'] = precision_deviations
    df_out['PRECISION_ALERT'] = precision_alerts
    
    if target_type == 'utm':
        df_out['UTM_ZONE'] = f"{target_utm_zone}{target_utm_hemi}"
    elif zones_out:
        df_out['UTM_ZONE'] = zones_out
        
    # Formatação das colunas numéricas de saída
    is_target_geo = (target_type == 'geo' or target_type == 'gms' or is_target_mgrs)
    
    # Se a saída for especificamente GMS, formatamos para String
    if target_type == 'gms':
        v_to_gms_lat = np.vectorize(lambda d: decimal_to_gms(d, is_lat=True))
        v_to_gms_lon = np.vectorize(lambda d: decimal_to_gms(d, is_lat=False))
        df_out['CONVERTED_X_TXT'] = v_to_gms_lon(df_out['CONVERTED_X'].to_numpy())
        df_out['CONVERTED_Y_TXT'] = v_to_gms_lat(df_out['CONVERTED_Y'].to_numpy())
    else:
        df_out['CONVERTED_X'] = df_out['CONVERTED_X'].round(8 if is_target_geo else 3)
        df_out['CONVERTED_Y'] = df_out['CONVERTED_Y'].round(8 if is_target_geo else 3)
        
    df_out['PRECISION_DEV_M'] = df_out['PRECISION_DEV_M'].round(6)
    
    # Sempre calcular as coordenadas geográficas WGS84 para plotagem direta no Leaflet
    if real_epsg_in == 4326:
        lons_map = xs_temp_in
        lats_map = ys_temp_in
    else:
        to_wgs84 = Transformer.from_crs(real_epsg_in, 4326, always_xy=True)
        lons_map, lats_map = to_wgs84.transform(xs_temp_in, ys_temp_in)
        
    df_out['MAP_LON'] = lons_map.round(8)
    df_out['MAP_LAT'] = lats_map.round(8)
    
    processing_time = time.time() - start_time
    
    return {
        "success": True,
        "message": "Conversão concluída com sucesso.",
        "total_points": len(df),
        "ignored_points": original_len - len(df),
        "stats": {
            "delimiter": "Tabulação" if delim == '\t' else "Ponto e Vírgula" if delim == ';' else "Vírgula",
            "time_s": round(processing_time, 4),
            "columns": {
                "id": col_id,
                "x": col_x,
                "y": col_y,
                "z": col_z
            }
        },
        "df_result": df_out
    }

def generate_kml_string(df, col_id, col_x, col_y, col_z=None, source_type='geo', source_datum='SIRGAS_2000', source_utm_zone=23, source_utm_hemi='S', local_params=None):
    """
    Gera a string XML KML correspondente para visualização em lote no Google Earth.
    """
    xs = df[col_x].to_numpy()
    ys = df[col_y].to_numpy()
    zs = df[col_z].to_numpy() if (col_z and col_z in df.columns) else np.zeros(len(df))
    
    if source_type == 'local' and local_params:
        v_transform = np.vectorize(transform_local_to_utm)
        xs_utm, ys_utm = v_transform(
            xs, ys, 
            origin_x=local_params.get('origin_x', 0.0), 
            origin_y=local_params.get('origin_y', 0.0), 
            rotation_deg=local_params.get('rotation', 0.0)
        )
        local_epsg = 31960 + int(local_params.get('zone', 23))
        trans_kml = Transformer.from_crs(local_epsg, 4326, always_xy=True)
        lons_kml, lats_kml = trans_kml.transform(xs_utm, ys_utm)
    else:
        if source_type == 'utm':
            epsg_in = get_utm_epsg(source_datum, source_utm_zone, source_utm_hemi)
        else:
            epsg_in = get_geographic_epsg(source_datum)
            
        if epsg_in != 4326:
            trans_kml = Transformer.from_crs(epsg_in, 4326, always_xy=True)
            lons_kml, lats_kml = trans_kml.transform(xs, ys)
        else:
            lons_kml = xs
            lats_kml = ys
            
    kml = []
    kml.append('<?xml version="1.0" encoding="UTF-8"?>')
    kml.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    kml.append('  <Document>')
    kml.append('    <name>meu-app-geo - Pontos Convertidos</name>')
    kml.append('    <description>Arquivo gerado com verificacao milimetrica de precisao.</description>')
    
    kml.append('    <Style id="normalPlacemark">')
    kml.append('      <IconStyle>')
    kml.append('        <color>ff00ff00</color>')
    kml.append('        <scale>0.8</scale>')
    kml.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>')
    kml.append('      </IconStyle>')
    kml.append('    </Style>')
    kml.append('    <Style id="alertPlacemark">')
    kml.append('      <IconStyle>')
    kml.append('        <color>ff0000ff</color>')
    kml.append('        <scale>1.0</scale>')
    kml.append('        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>')
    kml.append('      </IconStyle>')
    kml.append('    </Style>')
    
    for i, (_, row) in enumerate(df.iterrows()):
        pt_name = str(row[col_id])
        lon_val = lons_kml[i]
        lat_val = lats_kml[i]
        alt_val = zs[i]
        
        dev_val = row.get('PRECISION_DEV_M', 0.0)
        alert_val = row.get('PRECISION_ALERT', False)
        
        style = '#alertPlacemark' if alert_val else '#normalPlacemark'
        
        desc = (
            "<![CDATA["
            "<h3>Detalhes do Ponto</h3>"
            "<table border='1' cellpadding='4' style='border-collapse: collapse; font-family: sans-serif; font-size: 12px;'>"
            f"<tr><td><b>ID:</b></td><td>{pt_name}</td></tr>"
            f"<tr><td><b>Origem X:</b></td><td>{row[col_x]}</td></tr>"
            f"<tr><td><b>Origem Y:</b></td><td>{row[col_y]}</td></tr>"
            f"<tr><td><b>Convertido Lon (WGS84):</b></td><td>{lon_val:.8f}</td></tr>"
            f"<tr><td><b>Convertido Lat (WGS84):</b></td><td>{lat_val:.8f}</td></tr>"
            f"<tr><td><b>Elevacao Z:</b></td><td>{alt_val:.3f}m</td></tr>"
            f"<tr><td><b>Desvio (2cm):</b></td><td>{dev_val:.6f}m "
            f"({'<font color=\"red\"><b>ALERTA</b></font>' if alert_val else '<font color=\"green\">OK</font>'})</td></tr>"
            "</table>"
            "]]>"
        )
        
        kml.append('    <Placemark>')
        kml.append(f'      <name>{pt_name}</name>')
        kml.append(f'      <description>{desc}</description>')
        kml.append(f'      <styleUrl>{style}</styleUrl>')
        kml.append('      <Point>')
        kml.append('        <extrude>1</extrude>')
        kml.append('        <altitudeMode>relativeToGround</altitudeMode>')
        kml.append(f'        <coordinates>{lon_val:.8f},{lat_val:.8f},{alt_val:.3f}</coordinates>')
        kml.append('      </Point>')
        kml.append('    </Placemark>')
        
    kml.append('  </Document>')
    kml.append('</kml>')
    
    return "\n".join(kml)
