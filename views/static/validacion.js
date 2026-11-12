// VISTA (MVC) - logica de cliente para los puntos de control.
// Envia los Excel a /validar, muestra los chequeos uno a uno y, solo si todo
// pasa, habilita el boton para generar la nota tecnica.

(function () {
  const form = document.getElementById("form-validar");
  const btnValidar = document.getElementById("btn-validar");
  const panel = document.getElementById("panel-control");
  const lista = document.getElementById("lista-control");
  const resumen = document.getElementById("resumen-control");
  const formGenerar = document.getElementById("form-generar");

  const ICONO = { ok: "✓", advertencia: "!", error: "✕" };

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    btnValidar.disabled = true;
    btnValidar.textContent = "Validando…";
    panel.hidden = false;
    formGenerar.hidden = true;
    lista.innerHTML = "";
    resumen.innerHTML = '<p class="ayuda">Ejecutando puntos de control…</p>';
    panel.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const resp = await fetch("/validar", { method: "POST", body: new FormData(form) });
      const rep = await resp.json();

      if (!resp.ok || rep.error) {
        resumen.innerHTML =
          '<div class="alerta error">' + (rep.error || "No se pudo validar.") + "</div>";
        return;
      }

      // Mostrar los chequeos de forma progresiva
      for (const c of rep.checkpoints) {
        await esperar(280);
        lista.appendChild(itemControl(c));
      }
      await esperar(200);

      if (rep.ok) {
        const advert = rep.checkpoints.some((c) => c.estado === "advertencia");
        resumen.innerHTML =
          '<div class="alerta ok">Todos los puntos de control pasaron' +
          (advert ? " (con advertencias por revisar)." : ".") +
          " Ya puedes generar la nota técnica.</div>";
        prepararGeneracion(rep.token);
        formGenerar.hidden = false;
        formGenerar.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else {
        resumen.innerHTML =
          '<div class="alerta error">Se encontraron inconsistencias. ' +
          "Corrige los Excel marcados y vuelve a validar.</div>";
      }
    } catch (err) {
      resumen.innerHTML =
        '<div class="alerta error">Error de conexión al validar: ' + err + "</div>";
    } finally {
      btnValidar.disabled = false;
      btnValidar.textContent = "Validar archivos";
    }
  });

  function itemControl(c) {
    const li = document.createElement("li");
    li.className = "chk " + c.estado;
    li.innerHTML =
      '<span class="chk-ic">' + (ICONO[c.estado] || "") + "</span>" +
      '<span class="chk-txt"><b>' + c.punto + "</b><br><small>" + c.detalle + "</small></span>";
    return li;
  }

  function prepararGeneracion(token) {
    document.getElementById("token").value = token;
    document.getElementById("g-crecimiento").value = form.crecimiento.value;
    document.getElementById("g-ipc").value = form.ipc.value;
    document.getElementById("g-umbral").value = form.umbral.value;
    document.getElementById("g-periodo").value = form.periodo.value;
  }

  function esperar(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }
})();
