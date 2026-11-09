(() => {
  const racine = document.querySelector("[data-code]");
  if (!racine) return;

  const code = racine.dataset.code;
  const bouton = document.getElementById("btn-rejoindre");
  const message = document.getElementById("message");
  const cleJeton = "qcm.jeton." + code;

  async function rejoindre() {
    bouton.disabled = true;
    message.textContent = "Connexion…";
    const jeton = localStorage.getItem(cleJeton);
    try {
      const reponse = await fetch("/api/rejoindre/", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({code, jeton}),
      });
      const donnees = await reponse.json().catch(() => ({}));
      if (!reponse.ok || !donnees.ok) {
        message.textContent =
          donnees.raison === "code_inconnu"
            ? "Séance introuvable."
            : "Connexion impossible.";
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
  if (localStorage.getItem(cleJeton)) {
    rejoindre();
  }
})();
