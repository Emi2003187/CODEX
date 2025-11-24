from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MedicamentoCatalogoForm
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

    return render(
        request,
        "PAGES/medicamentos/medicamentos_lista.html",
        {
            "medicamentos": medicamentos,
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
