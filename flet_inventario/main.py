import flet as ft
import os
from dotenv import load_dotenv
from views.login.login_view import login_view

load_dotenv()

def main(page: ft.Page):
    page.title = "Sistema de Inventario"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0d0d0d"
    page.padding = 0
    page.spacing = 0
    page.add(login_view(page))

ft.app(target=main)
