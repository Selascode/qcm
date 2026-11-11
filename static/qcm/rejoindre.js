(() => {
  const racine = document.querySelector("[data-code]");
  if (!racine) return;

  const code = racine.dataset.code;
  const estGroupe = racine.dataset.groupe === "1";
  const bouton = document.getElementById("btn-rejoindre");
  const message = document.getElementById("message");
  const champId = document.getElementById("code_etudiant");
  const cleJeton = "qcm.jeton." + code;

  const parametres = new URLSearchParams(window.location.search);
  if (parametres.get("reconnect") === "1") {
    message.textContent = "Reconnectez-vous avec votre identifiant.";
  }

  async function rejoindre() {
    bouton.disabled = true;
    const corps = { code };

    if (estGroupe) {
      const identifiant = champId ? champId.value.trim() : "";
      if (!identifiant) {
        message.textContent = "Saisissez votre identifiant.";
        bouton.disabled = false;
        return;
      }
      corps.code_etudiant = identifiant;
      const jeton = sessionStorage.getItem(cleJeton);
      if (jeton) corps.jeton = jeton;
    } else {
      corps.jeton = sessionStorage.getItem(cleJeton);
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
        } else if (donnees.raison === "identifiant_inconnu") {
          message.textContent =
            "Identifiant inconnu. Vérifiez l'écran de pré-séance.";
        } else if (donnees.raison === "appareil_deja_utilise") {
          message.textContent =
            "Cet appareil est déjà utilisé par un autre élève. Utilisez votre propre appareil.";
        } else if (donnees.raison === "deja_connecte") {
          message.textContent =
            "Identifiant déjà connecté sur un autre appareil. Demandez au professeur de réinitialiser votre appareil.";
        } else {
          message.textContent = "Connexion impossible.";
        }
        bouton.disabled = false;
        return;
      }
      sessionStorage.setItem(cleJeton, donnees.jeton);
      window.location.href = "/eleve/" + encodeURIComponent(code) + "/";
    } catch (erreur) {
      message.textContent = "Réseau indisponible, réessayez.";
      bouton.disabled = false;
    }
  }

  bouton.addEventListener("click", rejoindre);
  if (!estGroupe && sessionStorage.getItem(cleJeton)) {
    rejoindre();
  }
})();
