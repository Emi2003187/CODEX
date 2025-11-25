import os
import tempfile

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CatalogoExcelForm, MedicamentoCatalogoForm
from .models import MedicamentoCatalogo
from .parsers import parsear_catalogo_excel


ADMIN_ROL = "admin"


def _verificar_admin(request):
    if request.user.rol != ADMIN_ROL:
        return False
    return True


def actualizar_catalogo_completo(lista):
    MedicamentoCatalogo.objects.all().delete()
    for item in lista:
        MedicamentoCatalogo.objects.create(**item)


@login_required
def importar_catalogo(request):
    if not _verificar_admin(request):
        return HttpResponseForbidden("Acceso restringido a administradores")

    actualizados = None
    progress_points = []

    if request.method == "POST":
        form = CatalogoExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
                for chunk in archivo.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            try:
                datos = parsear_catalogo_excel(temp_path)
                actualizar_catalogo_completo(datos)
                actualizados = len(datos)
                progress_points = [0, 20, 40, 60, 80, 100]
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    else:
        form = CatalogoExcelForm()

    contexto = {
        "usuario": request.user,
        "form": form,
        "actualizados": actualizados,
        "progress_points": progress_points,
    }
    return render(request, "PAGES/medicamentos/importar_catalogo.html", contexto)


@login_required
def medicamentos_lista(request):
    if not _verificar_admin(request):
        return HttpResponseForbidden("Acceso restringido a administradores")

    medicamentos = MedicamentoCatalogo.objects.all().order_by("nombre")
    return render(
        request,
        "PAGES/medicamentos/lista.html",
        {"medicamentos": medicamentos, "usuario": request.user},
    )


@login_required
def medicamento_crear(request):
    if not _verificar_admin(request):
        return HttpResponseForbidden("Acceso restringido a administradores")

    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm()

    return render(
        request,
        "PAGES/medicamentos/crear.html",
        {"form": form, "usuario": request.user},
    )


@login_required
def medicamento_editar(request, pk):
    if not _verificar_admin(request):
        return HttpResponseForbidden("Acceso restringido a administradores")

    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)
    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES, instance=medicamento)
        if form.is_valid():
            form.save()
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm(instance=medicamento)

    return render(
        request,
        "PAGES/medicamentos/editar.html",
        {"form": form, "usuario": request.user, "medicamento": medicamento},
    )


@login_required
def medicamento_eliminar(request, pk):
    if not _verificar_admin(request):
        return HttpResponseForbidden("Acceso restringido a administradores")

    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)
    if request.method == "POST":
        medicamento.delete()
        return redirect("medicamentos_lista")

    return render(
        request,
        "PAGES/medicamentos/eliminar.html",
        {"medicamento": medicamento, "usuario": request.user},
    )
