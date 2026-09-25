// Admin & Gatekeeping Controller - 100% Offline & Pure Vanilla JS
document.addEventListener("DOMContentLoaded", () => {
  // Tabs Navigation
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetTab);
      if (targetContent) targetContent.classList.add("active");

      // Auto-load data if tab opened
      if (targetTab === "tab-attendees") loadAttendees();
    });
  });

  // Web Audio Synthesizer (Zero external audio files needed!)
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

  function playTone(freq, duration, type = "sine") {
    try {
      if (audioCtx.state === "suspended") audioCtx.resume();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (e) {
      // Audio not permitted or supported
    }
  }

  function playSuccessSound() {
    playTone(587.33, 0.12, "triangle"); // D5
    setTimeout(() => playTone(880, 0.25, "triangle"), 120); // A5
  }

  function playWarningSound() {
    playTone(300, 0.15, "sawtooth");
    setTimeout(() => playTone(220, 0.35, "sawtooth"), 160);
  }

  // --- STATS ---
  const statRevenue = document.getElementById("stat-revenue");
  const statSold = document.getElementById("stat-sold");
  const statUsed = document.getElementById("stat-used");
  const statAvailable = document.getElementById("stat-available");
  const btnRefreshStats = document.getElementById("btn-refresh-stats");

  async function loadStats() {
    try {
      const res = await fetch("/api/admin/stats");
      if (!res.ok) return;
      const data = await res.json();
      statRevenue.innerText = `$${data.total_revenue.toFixed(2)}`;
      statSold.innerText = data.sold_tickets;
      statUsed.innerText = data.used_tickets;
      statAvailable.innerText = data.available_tickets;
    } catch (err) {
      console.error("Failed to load stats", err);
    }
  }

  btnRefreshStats.addEventListener("click", () => {
    loadStats();
    showToast("Métricas actualizadas", "info");
  });

  // --- QR CAMERA SCANNER ---
  const video = document.getElementById("scanner-video");
  const canvas = document.getElementById("scanner-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const btnToggleCamera = document.getElementById("btn-toggle-camera");
  const idleMsg = document.getElementById("scanner-idle-msg");

  let stream = null;
  let isScanning = false;
  let isCooldown = false;

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } }
      });
      video.srcObject = stream;
      video.setAttribute("playsinline", true);
      await video.play();
      isScanning = true;
      idleMsg.style.display = "none";
      btnToggleCamera.innerText = "Detener Cámara";
      btnToggleCamera.classList.remove("btn-secondary");
      btnToggleCamera.classList.add("btn-primary");
      requestAnimationFrame(scanTick);
    } catch (err) {
      alert("No se pudo acceder a la cámara: " + err.message + "\nPuedes usar el ingreso manual o lector USB a la derecha.");
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    isScanning = false;
    idleMsg.style.display = "block";
    btnToggleCamera.innerText = "Iniciar Cámara";
    btnToggleCamera.classList.remove("btn-primary");
    btnToggleCamera.classList.add("btn-secondary");
  }

  btnToggleCamera.addEventListener("click", () => {
    if (isScanning) stopCamera();
    else startCamera();
  });

  function scanTick() {
    if (!isScanning) return;

    if (video.readyState === video.HAVE_ENOUGH_DATA && !isCooldown) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      if (typeof jsQR !== "undefined") {
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: "dontInvert",
        });

        if (code && code.data) {
          isCooldown = true;
          handleVerification(code.data).finally(() => {
            // Wait 2.5s before reading next code to avoid continuous triggers
            setTimeout(() => { isCooldown = false; }, 2500);
          });
        }
      }
    }

    if (isScanning) {
      requestAnimationFrame(scanTick);
    }
  }

  // --- VERIFICATION HANDLER ---
  const manualVerifyForm = document.getElementById("manual-verify-form");
  const inputVerifyCode = document.getElementById("input-verify-code");
  const resultCard = document.getElementById("verify-result-card");
  const resultBadge = document.getElementById("verify-result-badge");
  const resultMsg = document.getElementById("verify-result-msg");
  const resultDetails = document.getElementById("verify-result-details");

  async function handleVerification(codeStr) {
    if (!codeStr || !codeStr.trim()) return;

    try {
      const res = await fetch("/api/admin/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: codeStr.trim() })
      });

      const data = await res.json();
      displayVerificationResult(data);
      loadStats(); // Update counters

    } catch (err) {
      displayVerificationResult({
        status: "INVALID",
        message: "Error de red al consultar el servidor local: " + err.message,
        ticket: null
      });
    }
  }

  function displayVerificationResult(data) {
    resultCard.style.display = "block";

    if (data.status === "VALID") {
      playSuccessSound();
      resultCard.style.background = "var(--success-light)";
      resultCard.style.borderColor = "var(--success)";
      resultBadge.style.color = "var(--success)";
      resultBadge.innerHTML = "&#10004; ENTRADA PERMITIDA (VÁLIDA)";
      resultMsg.innerText = data.message;

      if (data.ticket) {
        resultDetails.innerHTML = `
          <div><strong>Evento:</strong> ${escapeHtml(data.ticket.event_title || '')}</div>
          <div><strong>Titular:</strong> ${escapeHtml(data.ticket.buyer_name || 'Invitado')}</div>
          <div><strong>Asiento:</strong> <span style="font-weight: 700; color: var(--primary);">${escapeHtml(data.ticket.seat_number || 'General')}</span></div>
          <div><strong>ID Boleto:</strong> <span style="font-family: monospace;">${escapeHtml(data.ticket.id)}</span></div>
        `;
      }
    } else if (data.status === "ALREADY_USED") {
      playWarningSound();
      resultCard.style.background = "var(--danger-light)";
      resultCard.style.borderColor = "var(--danger)";
      resultBadge.style.color = "var(--danger)";
      resultBadge.innerHTML = "&#9888; ALERTA: BOLETO YA UTILIZADO";
      resultMsg.innerText = data.message;

      if (data.ticket) {
        resultDetails.innerHTML = `
          <div><strong>Titular Registrado:</strong> ${escapeHtml(data.ticket.buyer_name || '-')}</div>
          <div><strong>Asiento:</strong> ${escapeHtml(data.ticket.seat_number || 'General')}</div>
          <div style="color: var(--danger); font-weight: 700; margin-top: 0.35rem;">
            ¡DENEGAR ACCESO! Este código ya fue marcado como ingresado.
          </div>
        `;
      }
    } else {
      playWarningSound();
      resultCard.style.background = "var(--warning-light)";
      resultCard.style.borderColor = "var(--warning)";
      resultBadge.style.color = "var(--warning)";
      resultBadge.innerHTML = "&#10008; BOLETO INVÁLIDO";
      resultMsg.innerText = data.message;
      resultDetails.innerHTML = `<div>Verifica que el código corresponda a un boleto pagado.</div>`;
    }
  }

  manualVerifyForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const val = inputVerifyCode.value;
    inputVerifyCode.value = "";
    handleVerification(val);
  });

  // --- POS QUICK SALE ---
  const posSaleForm = document.getElementById("pos-sale-form");
  const posEventSelect = document.getElementById("pos-event-select");
  const posBuyerName = document.getElementById("pos-buyer-name");
  const posBuyerContact = document.getElementById("pos-buyer-contact");
  const posQuantity = document.getElementById("pos-quantity");
  const posTotalAmount = document.getElementById("pos-total-amount");
  const btnPosSubmit = document.getElementById("btn-pos-submit");

  function updatePosTotal() {
    const selectedOption = posEventSelect.options[posEventSelect.selectedIndex];
    const price = selectedOption ? parseFloat(selectedOption.getAttribute("data-price") || 0) : 0;
    const qty = parseInt(posQuantity.value, 10) || 1;
    posTotalAmount.innerText = `$${(price * qty).toFixed(2)}`;
  }

  if (posEventSelect) {
    posEventSelect.addEventListener("change", updatePosTotal);
    posQuantity.addEventListener("change", updatePosTotal);
    updatePosTotal();
  }

  if (posSaleForm) {
    posSaleForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      btnPosSubmit.disabled = true;
      btnPosSubmit.innerText = "Emitiendo boleto en taquilla...";

      try {
        const payload = {
          event_id: parseInt(posEventSelect.value, 10),
          quantity: parseInt(posQuantity.value, 10),
          buyer_name: posBuyerName.value.trim(),
          buyer_contact: posBuyerContact.value.trim() || "Taquilla Puerta",
          payment_method: "CASH"
        };

        const res = await fetch("/api/tickets/purchase", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error en la venta");

        showToast("¡Venta completada!", "success");
        loadStats();

        // Open first ticket in new tab for immediate printing
        if (data.tickets && data.tickets.length > 0) {
          window.open(`/ticket/${data.tickets[0].id}`, "_blank");
        }

        posBuyerName.value = "";
      } catch (err) {
        showToast(err.message, "danger");
      } finally {
        btnPosSubmit.disabled = false;
        btnPosSubmit.innerText = "Cobrar en Efectivo y Emitir Boleto";
      }
    });
  }

  // --- ATTENDEES TABLE ---
  const attendeesTableBody = document.getElementById("attendees-table-body");
  const filterTicketStatus = document.getElementById("filter-ticket-status");
  const filterTicketQuery = document.getElementById("filter-ticket-query");
  const btnFilterTickets = document.getElementById("btn-filter-tickets");

  async function loadAttendees() {
    attendeesTableBody.innerHTML = `
      <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Cargando...</td></tr>
    `;

    try {
      const statusParam = filterTicketStatus.value ? `&status_filter=${filterTicketStatus.value}` : "";
      const queryParam = filterTicketQuery.value ? `&query=${encodeURIComponent(filterTicketQuery.value.trim())}` : "";
      const res = await fetch(`/api/admin/tickets?limit=100${statusParam}${queryParam}`);
      if (!res.ok) throw new Error("Error loading attendees");
      const tickets = await res.json();

      if (!tickets || tickets.length === 0) {
        attendeesTableBody.innerHTML = `
          <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No se encontraron boletos.</td></tr>
        `;
        return;
      }

      attendeesTableBody.innerHTML = tickets.map(t => {
        let statusBadge = "";
        if (t.status === "SOLD") {
          statusBadge = `<span style="background: var(--primary-light); color: var(--primary); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; font-size: 0.75rem;">Vendido</span>`;
        } else if (t.status === "USED") {
          statusBadge = `<span style="background: var(--success-light); color: var(--success); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; font-size: 0.75rem;">Ingresado</span>`;
        } else {
          statusBadge = `<span style="background: #f1f5f9; color: var(--text-muted); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; font-size: 0.75rem;">${t.status}</span>`;
        }

        const usedTime = t.used_at ? new Date(t.used_at).toLocaleTimeString() : "-";

        return `
          <tr>
            <td style="font-family: monospace; font-size: 0.75rem;">${t.id.substring(0, 8)}...</td>
            <td><strong>${escapeHtml(t.event_title)}</strong></td>
            <td>${escapeHtml(t.seat_number)}</td>
            <td>${statusBadge}</td>
            <td>${escapeHtml(t.buyer_name)}</td>
            <td>${escapeHtml(t.buyer_contact)}</td>
            <td>${usedTime}</td>
            <td>
              <a href="/ticket/${t.id}" target="_blank" class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                Ver / Imprimir
              </a>
            </td>
          </tr>
        `;
      }).join("");

    } catch (err) {
      attendeesTableBody.innerHTML = `
        <tr><td colspan="8" style="text-align: center; color: var(--danger); padding: 1.5rem;">${err.message}</td></tr>
      `;
    }
  }

  btnFilterTickets.addEventListener("click", loadAttendees);
  filterTicketStatus.addEventListener("change", loadAttendees);

  // --- CREATE EVENT FORM ---
  const createEventForm = document.getElementById("create-event-form");
  const evHasSeats = document.getElementById("ev-has-seats");
  const seatPrefixContainer = document.getElementById("seat-prefix-container");
  const btnCreateEvent = document.getElementById("btn-create-event");

  evHasSeats.addEventListener("change", () => {
    seatPrefixContainer.style.display = evHasSeats.checked ? "block" : "none";
  });

  createEventForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    btnCreateEvent.disabled = true;
    btnCreateEvent.innerText = "Creando evento...";

    try {
      const payload = {
        title: document.getElementById("ev-title").value.trim(),
        description: document.getElementById("ev-desc").value.trim() || null,
        total_capacity: parseInt(document.getElementById("ev-capacity").value, 10),
        price: parseFloat(document.getElementById("ev-price").value),
        has_seat_numbers: evHasSeats.checked,
        seat_prefix: document.getElementById("ev-seat-prefix").value.trim() || "A"
      };

      const res = await fetch("/api/admin/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al crear evento");

      showToast(`¡Evento "${data.title}" creado con ${data.total_capacity} boletos!`, "success");
      createEventForm.reset();
      seatPrefixContainer.style.display = "none";
      loadStats();
      
      // Update POS select option
      const newOption = document.createElement("option");
      newOption.value = data.id;
      newOption.setAttribute("data-price", data.price);
      newOption.innerText = `${data.title} ($${data.price.toFixed(2)})`;
      posEventSelect.appendChild(newOption);

    } catch (err) {
      showToast(err.message, "danger");
    } finally {
      btnCreateEvent.disabled = false;
      btnCreateEvent.innerText = "Crear Evento e Inicializar Boletos";
    }
  });

  // Helpers
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    })[m]);
  }

  // Initial stats
  loadStats();
});
