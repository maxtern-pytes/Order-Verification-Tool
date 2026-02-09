# Add filters section to viewer.html

with open('d:/projects/offcmft2.0/templates/viewer.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line 183 which has "</div>" after bulk actions
# Insert filters section after it
filters_html = '''
            <!-- Filters Section -->
            <div class="bg-gray-50 rounded-lg p-4 mt-4">
                <form method="GET" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Start Date</label>
                        <input type="date" name="start_date" value="{{ start_date or '' }}"
                            class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">End Date</label>
                        <input type="date" name="end_date" value="{{ end_date or '' }}"
                            class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Payment</label>
                        <select name="payment" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm">
                            <option value="">All</option>
                            <option value="Prepaid" {{ 'selected' if payment == 'Prepaid' }}>Prepaid</option>
                            <option value="COD" {{ 'selected' if payment == 'COD' }}>COD</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Delivery</label>
                        <select name="delivery" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm">
                            <option value="">All</option>
                            <option value="Standard" {{ 'selected' if delivery == 'Standard' }}>Standard</option>
                            <option value="Express" {{ 'selected' if delivery == 'Express' }}>Express</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">State</label>
                        <select name="state" class="w-full px-2 py-1.5 border border-gray-300 rounded text-sm">
                            <option value="">All</option>
                            <option value="Delhi" {{ 'selected' if state == 'Delhi' }}>Delhi</option>
                            <option value="Maharashtra" {{ 'selected' if state == 'Maharashtra' }}>Maharashtra</option>
                            <option value="Karnataka" {{ 'selected' if state == 'Karnataka' }}>Karnataka</option>
                            <option value="Tamil Nadu" {{ 'selected' if state == 'Tamil Nadu' }}>Tamil Nadu</option>
                            <option value="Gujarat" {{ 'selected' if state == 'Gujarat' }}>Gujarat</option>
                            <option value="Rajasthan" {{ 'selected' if state == 'Rajasthan' }}>Rajasthan</option>
                            <option value="West Bengal" {{ 'selected' if state == 'West Bengal' }}>West Bengal</option>
                            <option value="Telangana" {{ 'selected' if state == 'Telangana' }}>Telangana</option>
                            <option value="Haryana" {{ 'selected' if state == 'Haryana' }}>Haryana</option>
                            <option value="Punjab" {{ 'selected' if state == 'Punjab' }}>Punjab</option>
                        </select>
                    </div>
                    <div class="md:col-span-2 lg:col-span-5 flex gap-2">
                        <button type="submit" class="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium">
                            Apply Filters
                        </button>
                        <a href="/viewer" class="px-4 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-sm font-medium">
                            Clear
                        </a>
                    </div>
                </form>
            </div>
'''

# Insert after line 183 (index 182)
lines.insert(183, filters_html)

with open('d:/projects/offcmft2.0/templates/viewer.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Added filters section to viewer.html!")
