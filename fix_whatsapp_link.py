# Fix WhatsApp link to add +91 country code

with open('d:/projects/offcmft2.0/templates/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the WhatsApp link to add 91 prefix
old_link = 'https://wa.me/{{ order.phone.replace'
new_link = 'https://wa.me/91{{ order.phone.replace'

content = content.replace(old_link, new_link)

with open('d:/projects/offcmft2.0/templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed WhatsApp link - added +91 country code!")
