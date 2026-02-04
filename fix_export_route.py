# Fix the incomplete export_confirmed route in app.py
# This script inserts the missing CSV fields after line 902

with open('d:/projects/offcmft2.0/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 902 which has: output.write(f'"{order.get("id","")}",'
# Insert the missing CSV fields after it
for i, line in enumerate(lines):
    if i == 902 and 'output.write(f\'"' in line and 'order.get("id"' in line:
        # Insert missing code after this line
        missing_lines = [
            '        output.write(f\'"{order.get("customer_name","")}",\')\n',
            '        output.write(f\'"{order.get("email","")}",\')\n',
            '        output.write(f\'"{order.get("phone","")}",\')\n',
            '        output.write(f\'"{address}",\')\n',
            '        output.write(f\'"{order.get("state","")}",\')\n',
            '        output.write(f\'"{order.get("payment_method","")}",\')\n',
            '        output.write(f\'"{products}",\')\n',
            '        output.write(f\'"{order.get("total","")}",\')\n',
            '        output.write(f\'"{order.get("delivery_type","")}",\')\n',
            '        output.write(f\'"{order.get("timestamp","")}\"\\n\')\n',
            '    \n',
            '    csv_data = output.getvalue()\n',
            '    output.close()\n',
            '    \n',
            '    response = Response(csv_data, mimetype=\'text/csv\')\n',
            '    response.headers[\'Content-Disposition\'] = f\'attachment; filename=confirmed_orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv\'\n',
            '    return response\n',
            '\n',
        ]
        
        # Insert after line 902
        lines = lines[:i+1] + missing_lines + lines[i+1:]
        
        # Write back
        with open('d:/projects/offcmft2.0/app.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print("✅ Fixed export_confirmed route successfully!")
        print(f"   Inserted {len(missing_lines)} lines after line {i+1}")
        break
else:
    print("❌ Could not find line 902 to fix")
