import flet as ft
from core.theme import ThemeColors, JetBrainsTheme
from components.status_badge import status_badge
from components.timeline import asset_timeline
from services.movement_service import get_asset_history, download_acta_entrega_recepcion
from services.user_service import list_crm_users
from core.api_client import APIClient
from core.session import Session
import threading
import webbrowser

def item_traceability_view(page: ft.Page, navigate, item_id=None, item_data=None):
    if not item_id:
        return ft.Container(content=ft.Text("ID de ítem no proporcionado", color=ft.colors.RED))

    # Estado local
    state = {
        "item": item_data or {},
        "movements": [],
        "loading": True
    }

    # Contenedores de UI
    timeline_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    header_container = ft.Container()
    loading_indicator = ft.ProgressBar(visible=True, color=ThemeColors.ACCENT_BLUE)

    def load_data():
        try:
            # 1. Cargar datos del ítem si no vienen en item_data
            if not state["item"]:
                res_item = APIClient.get(f"inventory/items/{item_id}/")
                state["item"] = res_item
            
            # 2. Cargar historial
            history_res = get_asset_history(item_id)
            state["movements"] = history_res.get("results", [])
            
            # 3. Renderizar
            render_header()
            render_timeline()
        except Exception as e:
            timeline_container.controls = [ft.Text(f"Error al cargar datos: {e}", color=ft.colors.RED_400)]
        finally:
            loading_indicator.visible = False
            page.update()

    def render_header():
        item = state["item"]

        def show_snack(msg: str, is_error: bool = False):
            page.snack_bar = ft.SnackBar(
                ft.Text(msg),
                bgcolor=ft.colors.RED_400 if is_error else ft.colors.GREEN_700,
            )
            page.snack_bar.open = True
            page.update()

        def open_acta_dialog(_):
            try:
                users = list_crm_users() or []
            except Exception as ex:
                show_snack(f"No se pudo cargar usuarios CRM: {ex}", True)
                return

            current_username = ""
            if Session.user and isinstance(Session.user, dict):
                current_username = str(Session.user.get("username") or "").strip()

            options = []
            for u in users:
                uid = str(u.get("id") or "").strip()
                username = str(u.get("username") or "").strip()
                if not uid or username == current_username:
                    continue
                full_name = (u.get("full_name") or username).strip()
                role_name = (u.get("role_name") or "Cargo no registrado").strip()
                options.append((uid, f"{full_name} | {role_name}"))

            if not options:
                show_snack("No hay usuarios CRM disponibles para 'Recibe'.", True)
                return

            recibe_dd = ft.Dropdown(
                label="Recibe (CRM)",
                width=430,
                value=options[0][0],
                options=[ft.dropdown.Option(key=k, text=t) for k, t in options],
            )
            obs_tf = ft.TextField(label="Observacion", multiline=True, min_lines=3, max_lines=4, width=430)

            def do_generate(__):
                payload = {
                    "recibe_user_id": str(recibe_dd.value or "").strip(),
                    "observacion": (obs_tf.value or "").strip(),
                    "item_id": item_id,
                    "item_ids": [item_id],
                }

                if not payload["recibe_user_id"]:
                    show_snack("Selecciona el usuario que recibe.", True)
                    return

                page.dialog.open = False
                page.update()

                def _worker():
                    try:
                        show_snack("Generando ACTA...")
                        pdf_path = download_acta_entrega_recepcion(payload)
                        webbrowser.open(f"file://{pdf_path}")
                        show_snack(f"ACTA generada y guardada en: {pdf_path}")
                    except Exception as ex:
                        show_snack(f"Error generando ACTA: {ex}", True)

                threading.Thread(target=_worker, daemon=True).start()

            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Generar ACTA DE ENTREGA - RECEPCION"),
                content=ft.Column([recibe_dd, obs_tf], tight=True),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda __: setattr(page.dialog, "open", False) or page.update()),
                    ft.ElevatedButton("Generar PDF", on_click=do_generate),
                ],
            )
            page.dialog.open = True
            page.update()

        header_container.content = ft.Container(
            **JetBrainsTheme.card_style(),
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.INVENTORY_ROUNDED, color=ThemeColors.ACCENT_BLUE, size=40),
                    padding=20, bgcolor=ft.colors.with_opacity(0.1, ThemeColors.ACCENT_BLUE),
                    border_radius=15
                ),
                ft.Column([
                    ft.Row([
                        ft.Text(item.get("nombre", "Cargando..."), size=24, weight="bold", color=ft.colors.WHITE),
                        status_badge(item.get("estado", "STOCK")),
                    ], spacing=15),
                    ft.Row([
                        ft.Text(f"CÓDIGO: {item.get('codigo','—')}", size=12, color=ThemeColors.TEXT_SECONDARY, weight="bold"),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"SERIAL: {item.get('serial','—')}", size=12, color=ThemeColors.TEXT_SECONDARY),
                        ft.Text("•", color=ThemeColors.TEXT_SECONDARY),
                        ft.Text(f"TIPO: {item.get('tipo_item','').upper()}", size=12, color=ThemeColors.TEXT_SECONDARY),
                    ], spacing=10)
                ], expand=True),
                ft.Row([
                    ft.ElevatedButton(
                        "ACTA ENTREGA-RECEPCION",
                        icon=ft.icons.PICTURE_AS_PDF,
                        on_click=open_acta_dialog,
                        style=JetBrainsTheme.primary_button_style()
                    ),
                    ft.ElevatedButton(
                        "Volver",
                        icon=ft.icons.ARROW_BACK,
                        on_click=lambda _: navigate("movements"),
                        style=JetBrainsTheme.secondary_button_style()
                    ),
                ], spacing=10)
            ], spacing=20)
        )

    def render_timeline():
        movements = state["movements"]
        timeline_entries = []
        
        for m in movements:
            prev = m.get("origen", {}).get("estado", "INICIO")
            curr = m.get("destino", {}).get("estado", "---")
            ot = m.get("ot_id")
            ot_str = f" [OT: {ot}]" if ot else ""
            
            timeline_entries.append({
                "date": m.get("fecha")[:16].replace("T", " "),
                "user": m.get("responsable", {}).get("username", "---"),
                "change": f"{prev} → {curr}{ot_str}",
                "notes": m.get("observaciones", "") or m.get("notes", "")
            })

        timeline_container.controls = [
            ft.Container(
                **JetBrainsTheme.card_style(),
                expand=True,
                padding=40,
                content=ft.Column([
                    ft.Text("HISTORIAL DE TRAZABILIDAD", size=18, weight="bold", color=ThemeColors.ACCENT_BLUE),
                    ft.Divider(height=30, color=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                    asset_timeline(timeline_entries)
                ], spacing=20)
            )
        ]

    # Ejecutar carga inicial
    import threading
    threading.Timer(0.1, load_data).start()

    return ft.Column([
        header_container,
        loading_indicator,
        timeline_container
    ], expand=True, spacing=20)
