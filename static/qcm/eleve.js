(() => {
  const racine = document.getElementById("app");
  if (!racine) return;

  const code = racine.dataset.code;
  const estGroupe = racine.dataset.groupe === "1";
  const cleJeton = "qcm.jeton." + code;
  const cleFile = "qcm.file." + code;

  const elStatut = document.getElementById("statut");
  const elMinuteur = document.getElementById("minuteur");
  const elQuestion = document.getElementById("question");
  const elAttente = document.getElementById("attente");
  const elFini = document.getElementById("fini");
  const elBadge = document.getElementById("badge-couleur");
  const elSymbole = document.getElementById("symbole");
  const elNomCouleur = document.getElementById("nom-couleur");
  const elBoutons = document.getElementById("boutons");
  const elValider = document.getElementById("valider");
  const elMessage = document.getElementById("message");

  let jeton = localStorage.getItem(cleJeton);
  let etat = null;
  let questionUid = null;
  let selection = new Set();
  let secondes = null;
  let intervalMinuteur = null;
  let delaiReessai = 1000;
  let minuterieFile = null;
  let envoiEnCours = false;
  let dernierMessage = "";

  function redirigerVersConnexion() {
    window.location.href =
      "/rejoindre/" + encodeURIComponent(code) + "/?reconnect=1";
  }

  if (estGroupe && !jeton) {
    window.location.href = "/rejoindre/" + encodeURIComponent(code) + "/";
    return;
  }

  const uuid = () => {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  };

  const lireFile = () => {
    try {
      const valeur = JSON.parse(localStorage.getItem(cleFile) || "[]");
      return Array.isArray(valeur) ? valeur : [];
    } catch (erreur) {
      return [];
    }
  };

  const ecrireFile = (file) => {
    localStorage.setItem(cleFile, JSON.stringify(file));
  };

  const message = (texte) => {
    if (dernierMessage === texte) return;
    dernierMessage = texte;
    elMessage.textContent = texte;
  };

  function afficherMinuteur() {
    if (secondes === null || secondes === undefined) {
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
    clearInterval(intervalMinuteur);
    if (actif && secondes !== null) {
      intervalMinuteur = setInterval(() => {
        if (secondes > 0) {
          secondes -= 1;
          afficherMinuteur();
        }
      }, 1000);
    }
  }

  function afficherBoutons(lettres, desactive) {
    elBoutons.innerHTML = "";
    for (const lettre of lettres) {
      const bouton = document.createElement("button");
      bouton.type = "button";
      bouton.className = "choix";
      bouton.textContent = lettre;
      bouton.dataset.lettre = lettre;
      bouton.disabled = desactive;
      bouton.setAttribute("aria-pressed", "false");
      bouton.addEventListener("click", () => {
        if (!etat || etat.statut !== "en_cours" || etat.deja_repondu) return;
        if (selection.has(lettre)) {
          selection.delete(lettre);
        } else {
          selection.add(lettre);
        }
        bouton.setAttribute(
          "aria-pressed",
          selection.has(lettre) ? "true" : "false"
        );
        elValider.disabled = selection.size === 0;
      });
      elBoutons.appendChild(bouton);
    }
  }

  function afficherQuestion(donnees) {
    if (!donnees || !donnees.question_uid || !donnees.couleur) {
      elQuestion.hidden = true;
      return;
    }
    elQuestion.hidden = false;
    elBadge.style.background = donnees.couleur.hex;
    elBadge.style.color = donnees.couleur.couleur_texte;
    elSymbole.textContent = donnees.symbole;
    elNomCouleur.textContent = donnees.couleur.nom;

    const enAttente = lireFile().some(
      (item) => item.question_uid === donnees.question_uid
    );
    const desactive =
      donnees.statut === "pause" ||
      donnees.deja_repondu ||
      donnees.statut === "fini" ||
      enAttente;

    if (donnees.question_uid !== questionUid) {
      questionUid = donnees.question_uid;
      selection = new Set();
      afficherBoutons(donnees.lettres, desactive);
      elValider.disabled = true;
    } else {
      elBoutons.querySelectorAll(".choix").forEach((bouton) => {
        bouton.disabled = desactive;
        bouton.setAttribute(
          "aria-pressed",
          selection.has(bouton.dataset.lettre) ? "true" : "false"
        );
      });
      elValider.disabled = desactive || selection.size === 0;
    }

    if (donnees.deja_repondu) {
      message("Votre réponse a bien été reçue.");
      elQuestion.classList.add("validee");
    } else {
      elQuestion.classList.remove("validee");
      if (enAttente) message("En attente d'envoi…");
    }
  }

  function afficherEtat(donnees) {
    etat = donnees;
    elAttente.hidden = true;
    elFini.hidden = true;

    if (donnees.statut === "attente") {
      elStatut.textContent = "En attente du démarrage…";
      elAttente.hidden = false;
      elQuestion.hidden = true;
      reglerMinuteur(null, false);
      return;
    }

    if (donnees.statut === "fini") {
      elStatut.textContent = "Séance terminée.";
      elFini.hidden = false;
      elQuestion.hidden = true;
      reglerMinuteur(null, false);
      ecrireFile([]);
      return;
    }

    if (donnees.statut === "pause") {
      elStatut.textContent = "Pause — le temps est suspendu.";
      reglerMinuteur(donnees.temps_restant_s, false);
    } else {
      elStatut.textContent = donnees.deja_repondu
        ? "Réponse validée."
        : "À vous de répondre.";
      reglerMinuteur(donnees.temps_restant_s, true);
    }

    afficherQuestion(donnees);

    if (donnees.deja_repondu) {
      ecrireFile(
        lireFile().filter(
          (item) => item.question_uid !== donnees.question_uid
        )
      );
    }
  }

  async function rejoindre() {
    if (estGroupe) {
      redirigerVersConnexion();
      throw new Error("reconnexion_requise");
    }
    const reponse = await fetch("/api/rejoindre/", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({code, jeton}),
    });
    const donnees = await reponse.json().catch(() => ({}));
    if (!reponse.ok || !donnees.ok) {
      throw new Error(donnees.raison || "rejoindre");
    }
    jeton = donnees.jeton;
    localStorage.setItem(cleJeton, jeton);
  }

  async function lireEtat() {
    if (!jeton) await rejoindre();
    const reponse = await fetch("/api/etat/", {
      headers: {"X-Jeton": jeton},
    });
    if (reponse.status === 401) {
      // Appareil remplacé ou jeton expiré : retour à l'écran de connexion.
      jeton = null;
      localStorage.removeItem(cleJeton);
      redirigerVersConnexion();
      return null;
    }
    if (!reponse.ok) throw new Error("etat");
    return reponse.json();
  }

  function retirerDeLaFile(idClient) {
    ecrireFile(lireFile().filter((item) => item.id_client !== idClient));
  }

  function planifierReessai() {
    clearTimeout(minuterieFile);
    message("En attente du réseau…");
    minuterieFile = setTimeout(envoyerFile, delaiReessai);
    delaiReessai = Math.min(30000, delaiReessai * 2);
  }

  async function envoyerFile() {
    if (envoiEnCours) return;
    const file = lireFile();
    if (!file.length) return;
    envoiEnCours = true;
    try {
      if (!jeton) await rejoindre();
      const item = file[0];
      const reponse = await fetch("/api/repondre/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Jeton": jeton,
        },
        body: JSON.stringify({
          id_client: item.id_client,
          question_uid: item.question_uid,
          choix: item.choix,
        }),
      });
      const donnees = await reponse.json().catch(() => ({}));
      if (reponse.status === 401) {
        jeton = null;
        localStorage.removeItem(cleJeton);
        redirigerVersConnexion();
        return;
      }
      if (reponse.ok && donnees.ok) {
        retirerDeLaFile(item.id_client);
        delaiReessai = 1000;
        message("Votre réponse a bien été reçue.");
        await rafraichir();
        setTimeout(envoyerFile, 300);
      } else if (donnees.raison === "seance_non_active") {
        planifierReessai();
      } else if (
        [
          "temps_ecoule",
          "deja_repondu",
          "mauvaise_question",
          "question_inconnue",
          "choix_invalide",
          "id_client_invalide",
        ].includes(donnees.raison)
      ) {
        retirerDeLaFile(item.id_client);
        message("Réponse non prise en compte.");
      } else {
        planifierReessai();
      }
    } catch (erreur) {
      planifierReessai();
    } finally {
      envoiEnCours = false;
    }
  }

  async function rafraichir() {
    try {
      const donnees = await lireEtat();
      if (donnees) afficherEtat(donnees);
    } catch (erreur) {
      // Hors ligne : l'état affiché reste, la file réessaiera.
    }
  }

  elValider.addEventListener("click", () => {
    if (!etat || etat.statut !== "en_cours" || etat.deja_repondu) return;
    if (!etat.question_uid || selection.size === 0) return;
    const item = {
      id_client: uuid(),
      question_uid: etat.question_uid,
      choix: [...selection],
      timestamp_local: Date.now(),
    };
    const file = lireFile();
    file.push(item);
    ecrireFile(file);
    selection = new Set();
    message("Envoi en cours…");
    afficherQuestion(etat);
    envoyerFile();
  });

  window.addEventListener("online", () => {
    delaiReessai = 1000;
    envoyerFile();
  });

  async function boucle() {
    await rafraichir();
    setTimeout(boucle, 1000 + Math.random() * 1000);
  }

  if (lireFile().length) {
    setTimeout(envoyerFile, 500);
  }
  boucle();
})();
