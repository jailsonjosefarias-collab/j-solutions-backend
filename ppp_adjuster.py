import re

def parse_ppp_report(file_content):
    """
    Realiza o parsing robusto do relatório em arquivo texto (.txt) do PPP IBGE,
    extraindo as coordenadas UTM corrigidas (Leste, Norte, Altitude Elipsoidal)
    ou Geográficas decimais se UTM não estiver no relatório.
    """
    coords = {
        'easting': None,
        'northing': None,
        'altitude': None,
        'latitude': None,
        'longitude': None
    }
    
    # Padrões de expressões regulares para buscar nos textos do relatório (Case Insensitive)
    patterns = {
        'northing': [
            r'norte\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'northing\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'norte\s*:?\s*([\d\.\,\-]+)'
        ],
        'easting': [
            r'leste\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'easting\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'leste\s*:?\s*([\d\.\,\-]+)'
        ],
        'altitude': [
            r'alt\.\s*elipsoidal\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'alt\s*elipsoidal\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'ellipsoidal\s*height\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'altitude\s*elipsoidal\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'altitude\s*elipsoidal\s*:?\s*([\d\.\,\-]+)',
            r'alt\.\s*elip\.\s*\(m\)\s*:?\s*([\d\.\,\-]+)',
            r'altitude\s*geometrica\s*\(m\)\s*:?\s*([\d\.\,\-]+)'
        ],
        'latitude': [
            r'latitude\s*\(gms\)\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'latitude\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lat\s*\(gms\)\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lat\s*:?\s*([\d\.\,\-\s°\'\"]+)'
        ],
        'longitude': [
            r'longitude\s*\(gms\)\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'longitude\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lon\s*\(gms\)\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lon\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lng\s*\(gms\)\s*:?\s*([\d\.\,\-\s°\'\"]+)',
            r'lng\s*:?\s*([\d\.\,\-\s°\'\"]+)'
        ]
    }
    
    # Processa linha a linha
    for line in file_content.split('\n'):
        line_lower = line.lower()
        for key, regex_list in patterns.items():
            if coords[key] is not None:
                continue
            for regex in regex_list:
                match = re.search(regex, line_lower)
                if match:
                    val_str = match.group(1).strip()
                    # Limpa formato numérico
                    val_str = val_str.replace(',', '.')
                    try:
                        coords[key] = float(val_str)
                    except ValueError:
                        coords[key] = val_str # Guarda string caso seja GMS
                    break
                    
    return coords
