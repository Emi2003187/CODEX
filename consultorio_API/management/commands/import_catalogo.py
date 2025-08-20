from django.core.management.base import BaseCommand
from django.conf import settings

from consultorio_API.catalogo_excel import buscar_articulos, catalogo_disponible
from consultorio_API.models import MedicamentoCatalogo


class Command(BaseCommand):
    help = "Importa o actualiza el catálogo de medicamentos desde el Excel"

    def handle(self, *args, **options):
        if not catalogo_disponible():
            self.stderr.write("Catálogo Excel no disponible")
            return

        data = buscar_articulos(q="", page=1, per_page=1000000)
        items = data.get("items", [])
        count = 0
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        for it in items:
            codigo = str(it.get("clave") or "").strip()
            if not codigo:
                continue
            defaults = {
                "nombre": it.get("nombre", "")[:255],
                "existencia": it.get("existencia", 0) or 0,
                "departamento": it.get("departamento") or None,
                "precio": it.get("precio") or None,
                "categoria": it.get("categoria") or None,
            }
            img_url = it.get("imagen_url")
            if img_url and img_url.startswith(media_url):
                defaults["imagen"] = img_url[len(media_url) :]
            MedicamentoCatalogo.objects.update_or_create(
                codigo_barras=codigo, defaults=defaults
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Procesados {count} registros"))
