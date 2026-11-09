(() => {
  const config = window.QCM_TABLEAU;
  if (!config) return;

  const code = config.code;
  const elMinuteur = document.getElementById("minuteur");
  const elEtape = document.getElementById("etape");
  const elReponses = document.getElementById("nb-reponses");
  const elParticipants = document.getElementById("nb-participants");
  let secondes = typeof config.temps === "number" ? config.temps : null;
  let interval = null;
  let etape = config.etape;
  let statut = config.statut;

  function afficherMinuteur() {
    if (secondes === null) {
      elMinuteur.textContent = "--:--";
      return;
    }
    const minutes = Math.floor(secondes / 60);
    const reste = secondes % 60;
    elMinuteur.textContent = minutes + ":" + String(reste).padStart(2, "0");
  }

  function reglerMinuteur(valeur, actif) {
    secondes = typeof valeur === "number" ? valeur : null;
    afficherMinuteur();
    clearInterval(interval);
    if (actif && secondes !== null) {
      interval = setInterval(() => {
        if (secondes > 0) {
          secondes -= 1;
          afficherMinuteur();
        }
      }, 1000);
    }
  }

  function getCookie(nom) {
    const prefixe = nom + "=";
    const morceau = document.cookie
      .split("; ")
      .find((ligne) => ligne.startsWith(prefixe));
    return morceau
      ? decodeURIComponent(morceau.slice(prefixe.length))
      : "";
  }

  async function piloter(action, delta) {
    try {
      const reponse = await fetch("/api/piloter/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({code, action, delta}),
      });
      const donnees = await reponse.json().catch(() => ({}));
      if (!reponse.ok || !donnees.ok) {
        alert("Action refusée : " + (donnees.raison || "erreur"));
        return;
      }
      window.location.reload();
    } catch (erreur) {
      alert("Réseau indisponible.");
    }
  }

  document.querySelectorAll("[data-action]").forEach((bouton) => {
    bouton.addEventListener("click", () => {
      const delta = bouton.dataset.delta
        ? Number(bouton.dataset.delta)
        : undefined;
      piloter(bouton.dataset.action, delta);
    });
  });

  async function rafraichir() {
    try {
      const reponse = await fetch(
        "/api/etat_prof/?code=" + encodeURIComponent(code)
      );
      if (!reponse.ok) return;
      const donnees = await reponse.json();
      if (donnees.etape !== etape || donnees.statut !== statut) {
        window.location.reload();
        return;
      }
      if (elEtape) elEtape.textContent = donnees.etape;
      if (elReponses) elReponses.textContent = donnees.nb_reponses_etape;
      if (elParticipants) {
        elParticipants.textContent = donnees.nb_participants;
      }
      for (const question of donnees.questions) {
        const compteur = document.querySelector(
          '[data-question-id="' + question.id + '"] [data-compteur]'
        );
        if (compteur) compteur.textContent = question.nb_reponses;
      }
      reglerMinuteur(
        donnees.temps_restant_s,
        donnees.statut === "en_cours"
      );
    } catch (erreur) {
      // Silence : le prochain poll réessaiera.
    } finally {
      setTimeout(rafraichir, 1000 + Math.random() * 1000);
    }
  }

  reglerMinuteur(config.temps, config.statut === "en_cours");
  setTimeout(rafraichir, 1000);
})();
