import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from converter import process_coordinate_conversion, parse_gms_to_decimal, decimal_to_gms

def run_gms_tests():
    print("=== INICIANDO VERIFICAÇÃO DE GMS E DATUMS ESTENDIDOS ===")
    
    # 1. Testar parser individual de strings GMS complexas
    test_cases = [
        ("19° 55' 18.8\" S", -19.92188889),
        ("43° 56' 16.2\" W", -43.93783333),
        ("23 33 01.8 S", -23.55050000),
        ("46 37 59.8 W", -46.63327778),
        ("-22 54 24.5", -22.90680556),
        ("15d47m39.1s S", -15.79419444),
        ("-30.0346", -30.03460000)
    ]
    
    print("\n[1] Testando interpretador Regex de GMS para Decimal...")
    parser_success = True
    for val_str, expected in test_cases:
        parsed = parse_gms_to_decimal(val_str)
        diff = abs(parsed - expected)
        if diff < 1e-5:
            print(f"  - OK: '{val_str}' -> {parsed:.8f} (Esperado: {expected:.8f})")
        else:
            print(f"  - FALHA: '{val_str}' -> {parsed:.8f} (Esperado: {expected:.8f}, Diff: {diff:.8f})")
            parser_success = False
            
    if not parser_success:
        print("ERRO: O parser de GMS falhou!")
        return False
        
    print("SUCESSO: Interpretador Regex de GMS aprovado!")
    
    # 2. Testar formatador de Decimal para GMS
    print("\n[2] Testando formatador de Decimal para GMS...")
    lat_dec = -23.5505
    lon_dec = -46.6333
    
    lat_gms = decimal_to_gms(lat_dec, is_lat=True)
    lon_gms = decimal_to_gms(lon_dec, is_lat=False)
    
    print(f"  - Lat: {lat_dec} -> {lat_gms}")
    print(f"  - Lon: {lon_dec} -> {lon_gms}")
    
    if "S" in lat_gms and "W" in lon_gms and "23° 33'" in lat_gms:
        print("SUCESSO: Formatador de GMS aprovado!")
    else:
        print("ERRO: Geração de string GMS incorreta!")
        return False
        
    # 3. Executar o processamento em lote da planilha com GMS de Entrada -> GMS de Saída
    print("\n[3] Executando processamento em lote de GMS -> GMS (SIRGAS 2000)...")
    test_file = os.path.join(os.path.dirname(__file__), "test_gms.txt")
    
    result = process_coordinate_conversion(
        file_path=test_file,
        source_type="gms",
        source_datum="SIRGAS_2000",
        target_type="gms",
        target_datum="SIRGAS_2000"
    )
    
    if not result["success"]:
        print(f"ERRO: Conversão falhou! Mensagem: {result['message']}")
        return False
        
    df = result["df_result"]
    print("SUCESSO: Conversão em lote concluída!")
    
    print("\nResultados do Lote:")
    for idx, row in df.iterrows():
        print(f"  - Ponto: {row['id']}")
        print(f"    Origem textiana X/Y: {row['long']} / {row['lat']}")
        print(f"    Saída formatada GMS E/N: {row['CONVERTED_X_TXT']} / {row['CONVERTED_Y_TXT']}")
        print(f"    Desvio de precisão (1cm): {row['PRECISION_DEV_M']:.8f} m (Alerta: {row['PRECISION_ALERT']})")
        
    print("\n=== TODOS OS TESTES ESTENDIDOS PASSARAM COM SUCESSO! ===")
    return True

if __name__ == "__main__":
    success = run_gms_tests()
    sys.exit(0 if success else 1)
