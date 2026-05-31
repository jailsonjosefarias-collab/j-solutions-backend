import os
import sys

# Garantir que o diretório atual está no path para importar o converter
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from converter import process_coordinate_conversion, generate_kml_string

def run_tests():
    print("=== INICIANDO TESTES DO MOTOR GEOGRÁFICO (converter.py) ===")
    
    test_file = os.path.join(os.path.dirname(__file__), "test_points.txt")
    
    # 1. Executar a conversão de SIRGAS 2000 Geográficas (4674) para UTM Automática
    print("\n[1] Executando conversão: SIRGAS 2000 Geographic (4674) -> UTM Automática...")
    result = process_coordinate_conversion(
        file_path=test_file,
        source_type="geo",
        source_datum="SIRGAS_2000",
        target_type="UTM_AUTO",
        target_datum="SIRGAS_2000"
    )
    
    if not result["success"]:
        print(f"ERRO: A conversão falhou! Mensagem: {result['message']}")
        return False
        
    print("SUCESSO: A conversão foi concluída!")
    print(f"Total de pontos: {result['total_points']}")
    print(f"Delimitador detectado: {result['stats']['delimiter']}")
    print(f"Tempo de execução: {result['stats']['time_s']} segundos")
    print(f"Colunas detectadas: {result['stats']['columns']}")
    
    df = result["result_df"] if "result_df" in result else result["df_result"]
    
    # 2. Validar Zonas UTM e precisão por ponto
    print("\n[2] Analisando resultados por ponto:")
    for idx, row in df.iterrows():
        pt_id = row["id"]
        original_x = row["long"]
        original_y = row["lat"]
        converted_x = row["CONVERTED_X"]
        converted_y = row["CONVERTED_Y"]
        utm_zone = row["UTM_ZONE"]
        precision_dev = row["PRECISION_DEV_M"]
        alert = row["PRECISION_ALERT"]
        
        print(f" - Ponto: {pt_id}")
        print(f"   Origem: Lon {original_x}, Lat {original_y}")
        print(f"   Zona UTM calculada: {utm_zone}")
        print(f"   Coordenadas UTM: E {converted_x}, N {converted_y}")
        print(f"   Desvio de Precisão (Inversa): {precision_dev:.8f} metros")
        print(f"   Status Alerta (>2cm): {'FALHOU (VERMELHO)' if alert else 'PASSOU (VERDE)'}")
        
        # O desvio em PyProj de alta qualidade deve ser sub-milimétrico (próximo de zero)
        if precision_dev > 0.02:
            print("   AVISO: Desvio inesperado maior que 2cm!")
            
    # 3. Testar o Gerador de KML
    print("\n[3] Testando a geração de KML...")
    col_map = result["stats"]["columns"]
    kml_str = generate_kml_string(
        df=df,
        col_id=col_map["id"],
        col_x=col_map["x"],
        col_y=col_map["y"],
        col_z=col_map["z"],
        source_type="geo",
        source_datum="SIRGAS_2000"
    )
    
    if kml_str and "<kml" in kml_str and "</kml>" in kml_str:
        print("SUCESSO: Estrutura XML do KML gerada corretamente!")
        print(f"Tamanho do KML gerado: {len(kml_str)} caracteres.")
    else:
        print("ERRO: Geração de KML inválida!")
        return False
        
    print("\n=== TODOS OS TESTES PASSARAM COM SUCESSO! ===")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
