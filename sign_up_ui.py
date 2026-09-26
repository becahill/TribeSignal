import customtkinter

class sign_up_ui(customtkinter.CTkFrame):
    def __init__(self, master, sign_up_success, open_login, user_db):
        super().__init__(master)
        
        self.sign_up_success = sign_up_success
        self.open_login = open_login
        self.user_db = user_db

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("green")

        self.label = customtkinter.CTkLabel(self, text="Tribe Signal Sign Up", font=("Roboto", 24))
        self.label.pack(pady=12, padx=10)

        self.username_entry = customtkinter.CTkEntry(self, placeholder_text="Username")
        self.username_entry.pack(pady=12, padx=10)

        self.password_entry = customtkinter.CTkEntry(self, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=12, padx=10)

        self.sign_up_button = customtkinter.CTkButton(self, text="Sign Up", command=self.register_sign_up)
        self.sign_up_button.pack(pady=12, padx=10)

        self.signup_button = customtkinter.CTkButton(
            self, 
            text="Back", 
            fg_color="transparent", 
            border_width=1, 
            command=self.open_login
        )
        self.signup_button.pack(pady=8, padx=10)

    def register_sign_up(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            self.label.configure(text="Fields cannot be empty", text_color="red")
            return

        if self.user_db.register(username, password):
            self.sign_up_success()
        else:
            self.label.configure(text="Username Taken", text_color="red")