import customtkinter

class main_ui(customtkinter.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=20, pady=20)

        customtkinter.set_appearance_mode("light")
        customtkinter.set_default_color_theme("green")

        self.theme_dropdown()

    def theme_dropdown(self, master=None):
        parent = master if master is not None else self

        self.dropdown_frame = customtkinter.CTkFrame(parent)
        self.dropdown_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="nsw")

        label = customtkinter.CTkLabel(master=self.dropdown_frame, text="Selected: Light")
        label.pack(pady=(10, 0))

        def dropdown_callback(choice):
            print(f"User selected: {choice}")
            customtkinter.set_appearance_mode(choice)
            label.configure(text=f"Selected: {choice}")

        options = ["System", "Light", "Dark"]

        combobox = customtkinter.CTkComboBox(
            master=self.dropdown_frame,
            values=options,
            command=dropdown_callback
        )
        combobox.set("Light") 
        combobox.pack(pady=10)