import customtkinter
from login_ui import login_ui as login
from sign_up_ui import sign_up_ui as sign
from main_interface_ui import main_ui as main
from users_storage import UserHashTable 

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Tribe Signal")
        self.geometry("500x400")

        # 2. Initialize the shared database instance HERE
        self.user_db = UserHashTable()
        self.user_db.register("admin", "1234")  # Pre-load default users if desired

        self.current_frame = None
        self.show_login_screen()

    def show_login_screen(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = login(
            self, 
            on_login_success=self.show_main_interface,
            open_signup=self.show_signup_screen,
            user_db=self.user_db
        )
        self.current_frame.pack(fill="both", expand=True)

    def show_signup_screen(self):
        if self.current_frame:
            self.current_frame.destroy()

        # Now self.user_db exists and won't throw an AttributeError!
        self.current_frame = sign(
            self,
            sign_up_success=self.show_login_screen,
            open_login=self.show_login_screen,
            user_db=self.user_db
        )
        self.current_frame.pack(fill="both", expand=True)

    def show_main_interface(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.current_frame = main(self)
        self.current_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()