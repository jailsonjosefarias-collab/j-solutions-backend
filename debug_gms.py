import re

def parse_gms_to_decimal(val):
    val_str = str(val).strip()
    val_str = re.sub(r'(\d+),(\d+)', r'\1.\2', val_str)
    
    # Extrair todos os números
    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', val_str)
    print("Numbers:", numbers)
    
    d = float(numbers[0])
    m = float(numbers[1]) if len(numbers) > 1 else 0.0
    s = float(numbers[2]) if len(numbers) > 2 else 0.0
    print(f"d: {d}, m: {m}, s: {s}")
    
    decimal = abs(d) + (m / 60.0) + (s / 3600.0)
    print("Decimal abs:", decimal)
    
    is_negative = False
    if d < 0 or '-' in numbers[0]:
        is_negative = True
    print("Is negative (step 1):", is_negative)
        
    val_upper = val_str.upper()
    print("val_upper:", val_upper)
    
    for h in ['S', 'SUL', 'W', 'WEST', 'O', 'OESTE']:
        if h in val_upper:
            print(f"Found negative hemi: {h}")
            is_negative = True
            
    for h in ['N', 'NORTE', 'E', 'EAST', 'L', 'LESTE']:
        if h in val_upper:
            print(f"Found positive hemi: {h}")
            is_negative = False
            
    print("Is negative (step 2):", is_negative)
    if is_negative:
        decimal = -decimal
    return decimal

print("Result:", parse_gms_to_decimal("-22 54 24.5"))
