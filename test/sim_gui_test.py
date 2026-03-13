import customtkinter as ctk
from PIL import Image, ImageTk
import cv2

root = ctk.CTk()
root.title("Robot Path Simulation")
root.geometry("800x600")

canvas = ctk.CTkCanvas(root, bg="black", highlightthickness=0)
canvas.pack(fill="both", expand=True)

img = cv2.imread('picture/edit/Nestle-full-edit02.pgm')
if img is not None:
    img = cv2.resize(img, (800, 600))
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    img_tk = ImageTk.PhotoImage(image=pil_img)
    canvas.create_image(0, 0, anchor="nw", image=img_tk)
    canvas.image = img_tk

def close():
    root.quit()

root.after(3000, close)
root.mainloop()
