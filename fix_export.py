# Script to fix the incomplete export_confirmed route in app.py

# Read the file
with open('d:/projects/offcmft2.0/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 903 which has the incomplete CSV writing
# Insert the missing CSV fields after it
insert_at = None
for i, line in enumerate(lines):
    if i >= 902 and 'output.write(f\'"' in line and 'order.get("id"' in line:
        insert_at = i + 1
        break

if insert_at:
    # Insert the missing CSV fields
    missing_code = [
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
    
    # Insert the code
    lines = lines[:insert_at] + missing_code + lines[insert_at:]
    
    # Write back
    with open('d:/projects/offcmft2.0/app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Fixed export_confirmed route successfully!")
else:
    print("Could not find the line to fix")
