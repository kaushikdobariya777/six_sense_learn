import getpass
from apps.user_auth.models import User

first_name = input("Please enter the user first name: ")
last_name = input("Please enter the user last name: ")
email = input("Please enter the user email: ")
password = getpass.getpass("Please enter the user password: ")
confirm_password = getpass.getpass("Please confirm the password: ")
if password == confirm_password:
    user = User.objects.create_user(email=email, password=password, name=first_name + " " + last_name)
else:
    print("Password and Confirm password do not match")
