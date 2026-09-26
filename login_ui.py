import customtkinter
from users_storage import UserHashTable as users

class login_ui(customtkinter.CTkFrame):
    def __init__(self, master, on_login_success, open_signup, user_db):
        super().__init__(master)

        self.on_login_success = on_login_success
        self.open_signup = open_signup
        self.user_db = user_db

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("green")

        self.user_db.register("admin", "1234")
        self.user_db.register("alex", "SecurePass99!")

        self.label = customtkinter.CTkLabel(self, text="Tribe Signal Login", font=("Roboto", 24))
        self.label.pack(pady=12, padx=10)

        self.username_entry = customtkinter.CTkEntry(self, placeholder_text="Username")
        self.username_entry.pack(pady=12, padx=10)

        self.password_entry = customtkinter.CTkEntry(self, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=12, padx=10)

        self.login_button = customtkinter.CTkButton(self, text="Login", command=self.check_login)
        self.login_button.pack(pady=12, padx=10)

        self.signup_button = customtkinter.CTkButton(
            self, 
            text="Sign Up", 
            fg_color="transparent", 
            border_width=1, 
            command=self.open_signup
        )
        self.signup_button.pack(pady=8, padx=10)

    def check_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if self.user_db.authenticate(username, password):
            self.on_login_success()
        else:
            self.label.configure(text="Invalid Credentials", text_color="red")