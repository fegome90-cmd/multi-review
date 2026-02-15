# Python file with style issues
def calculate_total(items):
    total=0
    for item in items:
        total = total + item['price']
    return total

def get_user_name(user):
    return user.name
