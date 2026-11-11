(() => {
  const racine = document.getElementById("app-participants");
  if (!racine) return;

  const code = racine.dataset.code;
  const corps = document.getElementById("lignes-participants");
  const compteur = document.getElementById("compteur");
  const champCsrf = document.querySelector("[name=csrfmiddlewaretoken]");
  const csrf = champCsrf ? champCsrf.value : "";

  const cle = (participant) =>
    participant.code_etudiant || "p-" + participant.participant_id;

  const texteActivite = (participant) => {
    const secondes = participant.derniere_activite_s;
    if (secondes === null || secondes === undefined) return "—";
    return "il y a " + secondes + " s";
  };

  function celluleStatut(participant) {
    const cellule = document.createElement("td");
    cellule.className = "statut-cell";
    const pastille = document.createElement("span");
    pastille.className =
      "pastille-statut " +
      (participant.connecte ? "connecte" : "non-connecte");
    pastille.textContent = participant.connecte ? "Connecté" : "Non connecté";
    cellule.appendChild(pastille);
    return cellule;
  }

  function celluleReset(participant) {
    const cellule = document.createElement("td");
    if (!participant.participant_id) return cellule;
    const formulaire = document.createElement("form");
    formulaire.method = "post";
    formulaire.action =
      "/session/" +
      encodeURIComponent(code) +
      "/participants/" +
      participant.participant_id +
      "/reinitialiser/";
    const jeton = document.createElement("input");
    jeton.type = "hidden";
    jeton.name = "csrfmiddlewaretoken";
    jeton.value = csrf;
    const bouton = document.createElement("button");
    bouton.type = "submit";
    bouton.className = "bouton-mini";
    bouton.textContent = "Réinitialiser";
    formulaire.append(jeton, bouton);
    cellule.appendChild(formulaire);
    return cellule;
  }

  function creerLigne(participant) {
    const ligne = document.createElement("tr");
    ligne.dataset.cle = cle(participant);
    for (const valeur of [participant.nom, participant.prenom]) {
      const cellule = document.createElement("td");
      cellule.textContent = valeur || "—";
      ligne.appendChild(cellule);
    }
    const identifiant = document.createElement("td");
    identifiant.className = "identifiant";
    identifiant.textContent = participant.code_etudiant || "—";
    ligne.appendChild(identifiant);
    ligne.appendChild(celluleStatut(participant));
    const activite = document.createElement("td");
    activite.className = "activite-cell";
    activite.textContent = texteActivite(participant);
    ligne.appendChild(activite);
    ligne.appendChild(celluleReset(participant));
    return ligne;
  }

  function mettreAJour(donnees) {
    if (compteur) {
      compteur.textContent = donnees.connectes + " / " + donnees.total;
    }

    const existantes = new Map(
      [...corps.querySelectorAll("tr[data-cle]")].map((ligne) => [
        ligne.dataset.cle,
        ligne,
      ])
    );
    const vues = new Set();

    for (const participant of donnees.participants) {
      const identifiant = cle(participant);
      vues.add(identifiant);
      let ligne = existantes.get(identifiant);
      if (!ligne) {
        ligne = creerLigne(participant);
        corps.appendChild(ligne);
        continue;
      }

      const statut = ligne.querySelector(".statut-cell");
      if (statut) statut.replaceWith(celluleStatut(participant));

      const activite = ligne.querySelector(".activite-cell");
      if (activite) activite.textContent = texteActivite(participant);

      const derniere = ligne.lastElementChild;
      if (
        participant.participant_id &&
        derniere &&
        !derniere.querySelector("form")
      ) {
        derniere.replaceWith(celluleReset(participant));
      }
    }

    for (const [identifiant, ligne] of existantes) {
      if (!vues.has(identifiant)) ligne.remove();
    }

    const vide = corps.querySelector(".table-vide");
    if (vide && donnees.participants.length) {
      const ligneVide = vide.closest("tr");
      if (ligneVide) ligneVide.remove();
    }
  }

  async function rafraichir() {
    try {
      const reponse = await fetch(
        "/api/etat_participants/?code=" + encodeURIComponent(code),
        { headers: { Accept: "application/json" } }
      );
      if (!reponse.ok) return;
      mettreAJour(await reponse.json());
    } catch (erreur) {
      // Réseau indisponible : on garde l'affichage courant.
    }
  }

  async function boucle() {
    await rafraichir();
    setTimeout(boucle, 1000 + Math.random() * 1000);
  }

  boucle();
})();
