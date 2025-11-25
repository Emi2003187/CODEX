import json
import os
import tempfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .catalogo_import import actualizar_inventario, parsear_catalogo_excel
from .forms import ExcelUploadForm, MedicamentoCatalogoForm
from .models import MedicamentoCatalogo


@login_required
def medicamentos_lista(request):
    if request.user.rol != "admin":
        messages.error(request, "Solo un administrador puede acceder a este módulo.")
        return redirect("home")

    termino = (request.GET.get("q") or "").strip()

    medicamentos = MedicamentoCatalogo.objects.all()
    if termino:
        medicamentos = medicamentos.filter(
            Q(nombre__icontains=termino)
            | Q(codigo_barras__icontains=termino)
            | Q(categoria__icontains=termino)
            | Q(departamento__icontains=termino)
        )

    medicamentos = medicamentos.order_by("nombre")

    paginator = Paginator(medicamentos, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "PAGES/medicamentos/medicamentos_lista.html",
        {
            "medicamentos": page_obj,
            "page_obj": page_obj,
            "usuario": request.user,
            "termino": termino,
        },
    )


@login_required
def medicamento_crear(request):
    if request.user.rol != "admin":
        messages.error(request, "Solo un administrador puede acceder a este módulo.")
        return redirect("home")

    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicamento creado correctamente.")
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm()

    return render(
        request,
        "PAGES/medicamentos/medicamento_crear.html",
        {
            "form": form,
            "usuario": request.user,
        },
    )


@login_required
def medicamento_editar(request, pk):
    if request.user.rol != "admin":
        messages.error(request, "Solo un administrador puede acceder a este módulo.")
        return redirect("home")

    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)

    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES, instance=medicamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicamento actualizado correctamente.")
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm(instance=medicamento)

    return render(
        request,
        "PAGES/medicamentos/medicamento_editar.html",
        {
            "form": form,
            "usuario": request.user,
            "medicamento": medicamento,
        },
    )


@login_required
def medicamento_eliminar(request, pk):
    if request.user.rol != "admin":
        messages.error(request, "Solo un administrador puede acceder a este módulo.")
        return redirect("home")

    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)

    if request.method == "POST":
        medicamento.delete()
        messages.success(request, "Medicamento eliminado correctamente.")
        return redirect("medicamentos_lista")

    return render(
        request,
        "PAGES/medicamentos/medicamento_eliminar.html",
        {
            "medicamento": medicamento,
            "usuario": request.user,
        },
    )


@login_required
def importar_catalogo(request):
    if request.user.rol != "admin":
        messages.error(request, "Solo un administrador puede acceder a este módulo.")
        return redirect("home")

    actualizados = None
    progress_points = []
    errores = []
    form = ExcelUploadForm()
    ruta_default = "/mnt/data/Catalogo de Artículos.xlsx"

    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        archivo = request.FILES.get("archivo")
        ruta_excel = ruta_default

        if archivo:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo.name)[1]) as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                ruta_excel = tmp.name

        if (not archivo and os.path.exists(ruta_excel)) or (archivo and form.is_valid()):
            try:
                datos = parsear_catalogo_excel(ruta_excel)
                actualizados = actualizar_inventario(datos)
                total = len(datos) or 1
                progress_points = [int((i / total) * 100) for i in range(1, total + 1)]
                if progress_points and progress_points[-1] < 100:
                    progress_points.append(100)
                messages.success(request, "Inventario actualizado con éxito")
            except Exception as exc:  # noqa: BLE001
                errores.append(str(exc))
                messages.error(request, "Ocurrió un error al importar el catálogo.")
            finally:
                if archivo:
                    try:
                        os.remove(ruta_excel)
                    except OSError:
                        pass
        else:
            if not os.path.exists(ruta_excel):
                errores.append("No se encontró el archivo de catálogo en la ruta predeterminada.")
            else:
                errores.append("Archivo inválido")

    return render(
        request,
        "PAGES/medicamentos/importar_catalogo.html",
        {
            "form": form,
            "usuario": request.user,
            "actualizados": actualizados,
            "progress_points": json.dumps(progress_points),
            "errores": errores,
        },
    )
