(() => {
  const racine = document.querySelector("[data-code]");
  if (!racine) return;

  const code = racine.dataset.code;
  const estGroupe = racine.dataset.groupe === "1";
  const bouton = document.getElementById("btn-rejoindre");
  const message = document.getElementById("message");
  const champId = document.getElementById("code_etudiant");
  const champPin = document.getElementById("pin");
  const cleJeton = "qcm.jeton." + code;

  const parametres = new URLSearchParams(window.location.search);
  if (parametres.get("reconnect") === "1") {
    message.textContent =
      "Reconnectez-vous avec votre identifiant et votre PIN.";
  }

  async function rejoindre() {
    bouton.disabled = true;
    const corps = { code };

    if (estGroupe) {
      const identifiant = champId ? champId.value.trim() : "";
      const pin = champPin ? champPin.value.trim() : "";
      if (!identifiant || !pin) {
        message.textContent = "Saisissez votre identifiant et votre PIN.";
        bouton.disabled = false;
        return;
      }
      if (!/^\d{4,6}$/.test(pin)) {
        message.textContent = "Le PIN doit contenir 4 à 6 chiffres.";
        bouton.disabled = false;
        return;
      }
      corps.code_etudiant = identifiant;
      corps.pin = pin;
    } else {
      corps.jeton = localStorage.getItem(cleJeton);
    }

    message.textContent = "Connexion…";
    try {
      const reponse = await fetch("/api/rejoindre/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corps),
      });
      const donnees = await reponse.json().catch(() => ({}));
      if (!reponse.ok || !donnees.ok) {
        if (donnees.raison === "code_inconnu") {
          message.textContent = "Séance introuvable.";
        } else if (donnees.raison === "identifiants_invalides") {
          message.textContent = "Identifiant ou PIN incorrect.";
        } else {
          message.textContent = "Connexion impossible.";
        }
        bouton.disabled = false;
        return;
      }
      localStorage.setItem(cleJeton, donnees.jeton);
      window.location.href = "/eleve/" + encodeURIComponent(code) + "/";
    } catch (erreur) {
      message.textContent = "Réseau indisponible, réessayez.";
      bouton.disabled = false;
    }
  }

  bouton.addEventListener("click", rejoindre);
  if (!estGroupe && localStorage.getItem(cleJeton)) {
    rejoindre();
  }
})();
