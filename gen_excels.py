import openpyxl

# 生成 small.xlsx
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Name", "Value"])
ws.append(["Alice", 10])
ws.append(["Bob", 20])
ws.append(["Carol", 30])
wb.save("small.xlsx")

# 生成 large.xlsx
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Name", "Value"])
for i in range(1, 100001):
    ws.append([f"User{i}", i])
wb.save("large.xlsx")
