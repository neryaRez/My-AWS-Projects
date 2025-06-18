from tkinterdnd2 import DND_FILES, TkinterDnD
import ttkbootstrap as ttk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import boto3

selected_file_path = None
selected_operation = None
processed_file_path = None
drop_img = None

def display_image(path):
    global selected_file_path, drop_img
    selected_file_path = path.strip('{}')
    try:
        img = Image.open(selected_file_path)

        frame_width, frame_height = 300,240

        # שינוי גודל התמונה בהתאמה למסגרת תוך שמירה על פרופורציות
        img.thumbnail((frame_width, frame_height))

        drop_img = ImageTk.PhotoImage(img)

        # מחיקת תמונות קודמות
        image_canvas.delete("all")

        # מסגרת כחולה קבועה
        image_canvas.create_rectangle(0, 0, frame_width, frame_height, outline="#0A84FF", width=4)

        # מיקום במרכז הקנבס
        image_canvas.create_image(frame_width // 2, frame_height // 2, image=drop_img, anchor="center")

        image_canvas.image = drop_img  # שמור רפרנס

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load image:\n{e}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load image:\n{e}")

def drop(event):
    display_image(event.data)

def browse():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if file_path:
        display_image(file_path)

def process_image():
    global processed_file_path
    if selected_file_path and selected_operation:
        img = Image.open(selected_file_path)
        if selected_operation == 'flip':
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif selected_operation == 'mirror':
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif selected_operation == 'grayscale':
            img = img.convert("L")
        processed_file_path = selected_file_path.replace(".", f"_{selected_operation}.", 1)
        img.save(processed_file_path)
        print(f"Processed image saved as: {processed_file_path}")
    else:
        messagebox.showerror("Error", "Please select an image and an operation first.")

def choose_operation(op):
    global selected_operation
    selected_operation = op
    process_image()
    if selected_operation:
        messagebox.showinfo("Operation Selected", f"Selected operation: {op}")
    print(f"Image path: {selected_file_path}")
    print(f"Operation: {selected_operation}")
    if processed_file_path:
        upload_to_s3()
        print(f"Uploading {processed_file_path} to S3 with operation {selected_operation}...")

def upload_to_s3():
    if not processed_file_path or not selected_operation:
        messagebox.showerror("Error", "Please select an image and an operation first.")
        return

    s3 = boto3.client('s3')
    bucket_name = 'cats-nerya-reznikov-455715798206-us-east-1'
    object_name = f"{selected_operation}/{selected_file_path.split('/')[-1]}"

    try:
        s3.upload_file(processed_file_path, bucket_name, object_name)
        print(f"✅ File uploaded to S3: s3://{bucket_name}/{object_name}")
        messagebox.showinfo("Success", "Image uploaded to S3!")
    except Exception as e:
        print(f"❌ Failed to upload: {e}")
        messagebox.showerror("Upload Failed", f"{e}")


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.style = ttk.Style("superhero")
        self.title("Cat Cloud 😺")
        self.geometry("1300x1300")
        self.configure(bg=self.style.colors.bg)

        # פונט פרופורציונלי
        self.update_idletasks()
        screen_h = self.winfo_screenheight()
        big_font = ("Helvetica", int(screen_h * 0.025))
        label_font = ("Helvetica", int(screen_h * 0.05))
        padding = int(screen_h * 0.015)

        # סגנונות כפתורים מותאמים אישית
        self.style.configure("Browse.TButton", font=big_font, foreground="white", background="#0A84FF", bordercolor="#0A84FF", relief="raised", borderwidth=3)
        self.style.configure("Flip.TButton", font=big_font, foreground="white", background="#28a745", bordercolor="#28a745", relief="solid", borderwidth=3)
        self.style.configure("Mirror.TButton", font=big_font, foreground="white", background="#FFA500", bordercolor="#FFA500", relief="solid", borderwidth=3)
        self.style.configure("Gray.TButton", font=big_font, foreground="white", background="#6C757D", bordercolor="#6C757D", relief="solid", borderwidth=3)

        # כותרת
        ttk.Label(self, text="Drag & Drop your image", font=label_font).pack(pady=padding * 2)

        # Drop Zone
        global image_canvas
        image_canvas = tk.Canvas(self, width=300, height=240, bg="white", highlightthickness=0)
        image_canvas.pack(pady=padding)
        image_canvas.create_rectangle(0, 0, 300, 240, outline="#0A84FF", width=4)

        # טקסט התחלה
        image_canvas.create_text(150, 120, text="Add your image here", fill="gray", font=("Helvetica", 18, "bold"), tags="placeholder")

        # תמיכה ב־Drag & Drop
        image_canvas.drop_target_register(DND_FILES)
        image_canvas.dnd_bind("<<Drop>>", drop)

        # Browse
        # כפתור Browse בצורת אליפסה
        canvas_browse = tk.Canvas(self, width=450, height=100, bg=self.style.colors.bg, highlightthickness=0)
        canvas_browse.pack(pady=padding)

        ellipse = canvas_browse.create_oval(10, 10, 440, 90, fill="#0A84FF", outline="")
        text = canvas_browse.create_text(225, 50, text="Browse Image", fill="white", font=("Helvetica", int(screen_h * 0.035), "bold"))

        def on_browse_click(event):
            browse()

        canvas_browse.tag_bind(ellipse, "<Button-1>", on_browse_click)
        canvas_browse.tag_bind(text, "<Button-1>", on_browse_click)

        # תת כותרת
        ttk.Label(self, text="Choose an operation", font=("Helvetica", int(screen_h * 0.04))).pack(pady=padding * 2)

        # כפתורים
        ttk.Button(self, text="Flip", style="Flip.TButton", width=30, padding=padding, command=lambda: choose_operation("flip")).pack(pady=padding)
        ttk.Button(self, text="Mirror", style="Mirror.TButton", width=30, padding=padding, command=lambda: choose_operation("mirror")).pack(pady=padding)
        ttk.Button(self, text="Grayscale", style="Gray.TButton", width=30, padding=padding, command=lambda: choose_operation("grayscale")).pack(pady=padding)
            
        # יציאה עם ESC
        self.bind("<Escape>", lambda e: self.destroy())
        


if __name__ == "__main__":
    app = App()
    app.mainloop()





