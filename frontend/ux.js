const $ = (selector) => document.querySelector(selector);
const safe = (value) => String(value).replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
const words = {
  en: {brandDescriptor:"Customer intelligence",eyebrow:"A FRESHER WAY TO UNDERSTAND CUSTOMERS",heroOne:"Better insight.",heroTwo:"Brighter decisions.",lede:"Explore retention, basket recommendations, and grounded assistance in one responsible decision workspace.",explore:"Explore the workspace",workspaceKicker:"THE WORKSPACE",workspaceTitle:"Intelligence you can use.",workspaceIntro:"Explore three model heads, service health, and how this demonstration handles data.",tabRetention:"Retention",tabRecommendations:"Recommendations",tabAssistant:"Assistant",tabOperations:"Operations",tabAbout:"About",retentionTitle:"Explore retention",horizon:"90-day horizon",retentionIntro:"Choose a synthetic scenario, then move a slider to see how the frozen model responds. Other features stay fixed in this illustrative profile. No customer is contacted automatically.",scenarioLabel:"Synthetic scenario",scenarioStarter:"Starter profile",scenarioFrequent:"Frequent shopper",scenarioLapsed:"Lapsed shopper",resetScenario:"Reset scenario",recencyLabel:"Days since last order",frequencyLabel:"Orders in observation period",spendLabel:"Total spend (illustrative units)",productsLabel:"Unique products",advancedToggle:"Advanced: view full model inputs",advancedNote:"For audit only: the sliders update selected fields; all other synthetic features remain fixed.",predictionWaiting:"Loading the synthetic profile…",basketTitle:"Build a basket",rulesBadge:"Explainable rules",basketIntro:"Search by product name or code, add items to a basket, and see what the offline rules recommend. Product codes remain visible for traceability.",searchLabel:"Search by product name or code",searchPlaceholder:"Try “parasol” or “15056BL”",searchHelp:"Start typing; results update automatically.",yourBasket:"Your basket",clearBasket:"Clear basket",recommendCount:"Recommendations",recommendButton:"See recommendations",recommendWaiting:"Add a product or try the empty-basket popularity fallback.",aboutKicker:"ABOUT THIS DEMONSTRATION",aboutTitle:"Transparent by design",provenanceTitle:"Data provenance",provenanceText:"Boréal Marché is a fictional pedagogical scenario based on the public UCI Online Retail II dataset—not proprietary client data.",dataCard:"Read the data card",modelTitle:"Model and limits",modelText:"The retention score supports human review; it is not an automated decision or a guarantee. Recommendations come from offline-mined rules with a popularity fallback.",modelCard:"Read the model card",privacyTitle:"Privacy notice",privacyText:"This demo uses synthetic profiles. Account-specific requests require identity verification; another customer's data must not be disclosed.",privacyLink:"Read the bilingual privacy notice",architectureTitle:"Architecture",architectureText:"One FastAPI service hosts the interface, prediction pipeline, recommendation index, and grounded assistant.",architectureLink:"View architecture diagram",footer:"Boreal Marche · D4 deployment demonstration",apiDocs:"API documentation",ready:"All heads ready",degraded:"Service degraded",unavailable:"Service unavailable",probability:"Return probability",eligible:"Campaign eligible",threshold:"Frozen threshold",version:"Model version",yes:"Yes",no:"No",predictionFailed:"Prediction failed",updating:"Updating probability…",found:"products found; showing",searchFailed:"Product search unavailable",noProducts:"No matching products. Try another name or code.",add:"Add",remove:"Remove",basketEmpty:"Your basket is empty. Recommendations use the popularity fallback.",rules:"Association rules",emptyFallback:"Popular products (empty basket)",noMatchFallback:"Popular products (no matching rule)",because:"Because you added",fallbackExplanation:"No association rule matched this basket. These are popular products, not personalized suggestions.",recommendFailed:"Recommendation failed",noRecommendations:"No recommendations available.",assistantFailed:"Assistant request failed",sources:"Sources",refused:"Refused",handoff:"Handoff",answered:"Answered",alert:"Alert active",normal:"Normal",normalStart:"Generating normal traffic…",normalDone:"Normal traffic complete.",shiftStart:"Generating intentionally invalid traffic…",shiftDone:"Shifted traffic complete; invalid contracts were rejected as designed."},
  fr: {brandDescriptor:"Intelligence client",eyebrow:"UNE NOUVELLE FAÇON DE COMPRENDRE LA CLIENTÈLE",heroOne:"De meilleures idées.",heroTwo:"Des décisions éclairées.",lede:"Explorez la fidélisation, les recommandations de panier et l'assistance fondée sur des sources dans un même espace responsable.",explore:"Explorer l'espace de travail",workspaceKicker:"ESPACE DE TRAVAIL",workspaceTitle:"Des informations utiles.",workspaceIntro:"Explorez trois modèles, la santé du service et la façon dont cette démonstration traite les données.",tabRetention:"Fidélisation",tabRecommendations:"Recommandations",tabAssistant:"Assistant",tabOperations:"Surveillance",tabAbout:"À propos",retentionTitle:"Explorer la fidélisation",horizon:"Horizon de 90 jours",retentionIntro:"Choisissez un scénario fictif, puis déplacez un curseur pour voir la réponse du modèle figé. Les autres variables restent fixes. Aucun client n'est contacté automatiquement.",scenarioLabel:"Scénario fictif",scenarioStarter:"Profil de départ",scenarioFrequent:"Client fréquent",scenarioLapsed:"Client inactif",resetScenario:"Réinitialiser",recencyLabel:"Jours depuis la dernière commande",frequencyLabel:"Commandes pendant la période d'observation",spendLabel:"Dépenses totales (unités indicatives)",productsLabel:"Produits distincts",advancedToggle:"Avancé : voir toutes les variables",advancedNote:"Pour vérification seulement : les curseurs modifient certaines variables; les autres restent fixes.",predictionWaiting:"Chargement du profil fictif…",basketTitle:"Composer un panier",rulesBadge:"Règles explicables",basketIntro:"Cherchez par nom ou code de produit, ajoutez des articles au panier et consultez les suggestions des règles hors ligne. Les codes restent visibles pour la traçabilité.",searchLabel:"Rechercher par nom ou code de produit",searchPlaceholder:"Essayez « parasol » ou « 15056BL »",searchHelp:"Commencez à écrire; les résultats sont actualisés automatiquement.",yourBasket:"Votre panier",clearBasket:"Vider le panier",recommendCount:"Suggestions",recommendButton:"Voir les recommandations",recommendWaiting:"Ajoutez un produit ou essayez les produits populaires avec un panier vide.",aboutKicker:"À PROPOS DE LA DÉMONSTRATION",aboutTitle:"La transparence avant tout",provenanceTitle:"Provenance des données",provenanceText:"Boréal Marché est un scénario pédagogique fictif fondé sur le jeu de données public UCI Online Retail II, et non sur des données exclusives d'un client.",dataCard:"Lire la fiche de données",modelTitle:"Modèle et limites",modelText:"Le score de fidélisation appuie une révision humaine; ce n'est ni une décision automatisée ni une garantie. Les suggestions proviennent de règles extraites hors ligne, avec repli sur la popularité.",modelCard:"Lire la fiche du modèle",privacyTitle:"Avis de confidentialité",privacyText:"Cette démonstration utilise des profils fictifs. Une vérification d'identité est requise pour les demandes liées à un compte; les données d'un autre client ne doivent pas être divulguées.",privacyLink:"Lire l'avis bilingue",architectureTitle:"Architecture",architectureText:"Un service FastAPI héberge l'interface, le modèle de prédiction, l'index de recommandations et l'assistant fondé sur des sources.",architectureLink:"Voir le schéma d'architecture",footer:"Boréal Marché · Démonstration de déploiement D4",apiDocs:"Documentation API",ready:"Tous les modules sont prêts",degraded:"Service dégradé",unavailable:"Service indisponible",probability:"Probabilité de retour",eligible:"Admissible à la campagne",threshold:"Seuil figé",version:"Version du modèle",yes:"Oui",no:"Non",predictionFailed:"Échec de la prédiction",updating:"Mise à jour de la probabilité…",found:"produits trouvés; affichage de",searchFailed:"Recherche de produits indisponible",noProducts:"Aucun produit trouvé. Essayez un autre nom ou code.",add:"Ajouter",remove:"Retirer",basketEmpty:"Votre panier est vide. Les suggestions utilisent les produits populaires.",rules:"Règles d'association",emptyFallback:"Produits populaires (panier vide)",noMatchFallback:"Produits populaires (aucune règle)",because:"Parce que vous avez ajouté",fallbackExplanation:"Aucune règle ne correspond à ce panier. Ces produits sont populaires, mais non personnalisés.",recommendFailed:"Échec de la recommandation",noRecommendations:"Aucune recommandation disponible.",assistantFailed:"Échec de la demande",sources:"Sources",refused:"Refusé",handoff:"Transfert",answered:"Répondu",alert:"Alerte active",normal:"Normal",normalStart:"Génération du trafic normal…",normalDone:"Trafic normal terminé.",shiftStart:"Génération du trafic invalide…",shiftDone:"Trafic modifié terminé; les demandes invalides ont été rejetées comme prévu."}
};
Object.assign(words.en,{assistantTitle:"Grounded bilingual assistant",assistantBadge:"Policy constrained",assistantIntro:"Ask a supported policy, product, recommendation, or retention question. Unsupported or sensitive requests should be refused or handed off.",questionLabel:"Your question",questionPlaceholder:"What is the return policy?",verifiedLabel:"Customer identity is verified for this demonstration",providerNote:"This live demonstration uses the deterministic rule-based provider. Hosted and local LLMs were evaluated separately; provider switching and streaming are not deployed here yet.",askButton:"Ask assistant",assistantWaiting:"The grounded answer, intent, citations, and safety outcome will appear here.",opsKicker:"OPERATIONS",opsTitle:"Live service monitoring",requests:"Requests",errors:"Errors",errorRate:"Error rate",latency:"Average latency",demoTraffic:"Demonstration traffic",trafficIntro:"Normal traffic exercises healthy endpoints. Shifted traffic intentionally violates the prediction contract to trigger observable errors.",generateNormal:"Generate normal traffic",generateShifted:"Generate shifted traffic",metricsRefresh:"Metrics refresh every five seconds."});
Object.assign(words.fr,{assistantTitle:"Assistant bilingue fondé sur des sources",assistantBadge:"Limité par les politiques",assistantIntro:"Posez une question sur une politique, un produit, une recommandation ou la fidélisation. Les demandes non prises en charge ou sensibles doivent être refusées ou transférées.",questionLabel:"Votre question",questionPlaceholder:"Quelle est la politique de retour?",verifiedLabel:"L'identité du client a été vérifiée pour cette démonstration",providerNote:"Cette démonstration utilise le fournisseur déterministe fondé sur des règles. Les modèles hébergé et local ont été évalués séparément; le choix du fournisseur et la diffusion progressive ne sont pas encore déployés.",askButton:"Demander à l'assistant",assistantWaiting:"La réponse, l'intention, les sources et le résultat de sécurité apparaîtront ici.",opsKicker:"SURVEILLANCE",opsTitle:"Surveillance du service",requests:"Demandes",errors:"Erreurs",errorRate:"Taux d'erreur",latency:"Latence moyenne",demoTraffic:"Trafic de démonstration",trafficIntro:"Le trafic normal vérifie les points de terminaison. Le trafic modifié viole volontairement le contrat de prédiction pour déclencher des erreurs observables.",generateNormal:"Générer le trafic normal",generateShifted:"Générer le trafic modifié",metricsRefresh:"Les mesures sont actualisées toutes les cinq secondes."});
words.en.itemFallback = "Added to complete the list using overall popularity.";
words.fr.itemFallback = "Ajouté pour compléter la liste selon la popularité générale.";
Object.assign(words.en,{journeyKicker:"GUIDED JOURNEY · STEP 2",journeyTitle:"Continue with an example basket",journeyDisclosure:"Head B is a separate model. This example basket is not generated from the retention profile and the retention score does not influence its recommendations.",journeyButton:"Load example basket and continue",journeyArrived:"Guided example loaded",journeyReminder:"This illustrative basket is independent of the synthetic profile in Head A.",journeyFailed:"The guided basket could not be loaded."});
Object.assign(words.fr,{journeyKicker:"PARCOURS GUIDÉ · ÉTAPE 2",journeyTitle:"Continuer avec un panier d'exemple",journeyDisclosure:"Le module B est un modèle distinct. Ce panier d'exemple n'est pas généré à partir du profil de fidélisation, et le score de fidélisation n'influence pas ses recommandations.",journeyButton:"Charger le panier d'exemple et continuer",journeyArrived:"Exemple guidé chargé",journeyReminder:"Ce panier illustratif est indépendant du profil fictif du module A.",journeyFailed:"Le panier guidé n'a pas pu être chargé."});
Object.assign(words.en,{browseProducts:"BROWSE PRODUCTS",chooseProducts:"Choose products to add",showAll:"Show all",orderSummary:"ORDER SUMMARY",item:"item",items:"items"});
Object.assign(words.fr,{browseProducts:"PARCOURIR LES PRODUITS",chooseProducts:"Choisissez les produits à ajouter",showAll:"Tout afficher",orderSummary:"SOMMAIRE DE LA COMMANDE",item:"article",items:"articles"});
Object.assign(words.en,{categoryLabel:"Browse by category",categoryAll:"All categories",categoryKitchenDining:"Kitchen & dining",categoryBagsStorage:"Bags & storage",categoryStationeryCrafts:"Stationery & crafts",categoryHomeDecor:"Home décor",categoryGiftsSeasonal:"Gifts & seasonal",categoryAccessories:"Accessories",categoryOther:"Other products",previousPage:"Previous",nextPage:"Next",showingRange:"Showing {start}–{end} of {total} products",pageOf:"Page {page} of {pages}"});
Object.assign(words.fr,{categoryLabel:"Parcourir par catégorie",categoryAll:"Toutes les catégories",categoryKitchenDining:"Cuisine et salle à manger",categoryBagsStorage:"Sacs et rangement",categoryStationeryCrafts:"Papeterie et loisirs créatifs",categoryHomeDecor:"Décoration intérieure",categoryGiftsSeasonal:"Cadeaux et articles saisonniers",categoryAccessories:"Accessoires",categoryOther:"Autres produits",previousPage:"Précédent",nextPage:"Suivant",showingRange:"Produits {start} à {end} sur {total}",pageOf:"Page {page} sur {pages}"});
Object.assign(words.en,{retentionIntro:"Choose a preset or adjust the sliders to create a coherent custom profile, then submit it for prediction. Related model features are recalculated automatically. No customer is contacted automatically.",scenarioCustom:"Custom profile",resetScenario:"Reset selected preset",predictButton:"Predict return probability",predictionReady:"Profile ready. Select Predict return probability to run the model.",predictionChanged:"Custom profile ready. Related model features were recalculated; select Predict return probability to run the model.",recommendationsForBasket:"Recommended for this basket",fallbackExplanation:"No basket-specific association rule matched these products. Showing popular products instead so the recommendation area is never left unexplained.",eligible:"Campaign target",yes:"Yes — lower natural return likelihood",no:"No — likely to return without outreach",advancedNote:"For audit only: dependent activity, basket, cadence, and ratio features are recalculated from the four visible controls.",eligibleWhy:"Why Yes: the predicted return probability ({probability}) is at or below the 40.0% campaign threshold. This customer is less likely to return naturally and may benefit from retention outreach.",notEligibleWhy:"Why No: the predicted return probability ({probability}) is above the 40.0% campaign threshold. This customer is more likely to return without retention outreach."});
Object.assign(words.fr,{retentionIntro:"Choisissez un profil prédéfini ou ajustez les curseurs pour créer un profil personnalisé cohérent, puis soumettez-le au modèle. Les variables connexes sont recalculées automatiquement. Aucun client n'est contacté automatiquement.",scenarioCustom:"Profil personnalisé",resetScenario:"Réinitialiser le profil sélectionné",predictButton:"Prédire la probabilité de retour",predictionReady:"Le profil est prêt. Sélectionnez Prédire la probabilité de retour pour exécuter le modèle.",predictionChanged:"Le profil personnalisé est prêt. Les variables connexes ont été recalculées; sélectionnez Prédire la probabilité de retour pour exécuter le modèle.",recommendationsForBasket:"Recommandations pour ce panier",fallbackExplanation:"Aucune règle d'association propre à ce panier ne correspond à ces produits. Des produits populaires sont affichés à la place afin que le résultat soit toujours expliqué.",eligible:"Cible de campagne",yes:"Oui — probabilité de retour naturel plus faible",no:"Non — retour probable sans intervention",advancedNote:"Pour vérification seulement : les variables connexes d'activité, de panier, de cadence et de ratio sont recalculées à partir des quatre contrôles visibles.",eligibleWhy:"Pourquoi Oui : la probabilité de retour prévue ({probability}) est égale ou inférieure au seuil de campagne de 40,0 %. Cette personne est moins susceptible de revenir naturellement et pourrait bénéficier d'une mesure de fidélisation.",notEligibleWhy:"Pourquoi Non : la probabilité de retour prévue ({probability}) dépasse le seuil de campagne de 40,0 %. Cette personne est plus susceptible de revenir sans mesure de fidélisation."});
Object.assign(words.en,{validationMethod:"Validation method",temporalModel:"Temporal validation (primary)",randomModel:"80/20 full cleaned data (random state 42)",temporalNote:"Primary model: training and evaluation follow time order to resemble future use.",randomNote:"Supplementary experiment: 790,960 cleaned transaction lines became customer snapshots. Customers were split 80/20 with seed 42; seven model families competed. The 40% cutoff is illustrative here.",modelUsed:"Model used",randomResultNote:"The 80/20 model was selected by internal validation. Its random holdout does not measure future-time performance. The 40% campaign decision is illustrative.",winningFamily:"Selected family"});
Object.assign(words.fr,{validationMethod:"Méthode de validation",temporalModel:"Validation temporelle (principale)",randomModel:"Données nettoyées 80/20 (état aléatoire 42)",temporalNote:"Modèle principal : l'entraînement et l'évaluation suivent l'ordre chronologique pour représenter un usage futur.",randomNote:"Expérience complémentaire : 790 960 lignes de transactions nettoyées ont servi à créer des profils clients. Les clients ont été répartis 80/20 avec la graine 42; sept familles de modèles ont été comparées. Le seuil de 40 % est illustratif ici.",modelUsed:"Modèle utilisé",randomResultNote:"Le modèle 80/20 a été choisi sur la validation interne. Son échantillon aléatoire ne mesure pas la performance future dans le temps. La décision au seuil de 40 % est illustrative.",winningFamily:"Famille retenue"});
Object.assign(words.en,{scenarioNotEligible:"Likely to return — not eligible"});
Object.assign(words.fr,{scenarioNotEligible:"Retour probable — non admissible"});
Object.assign(words.en,{decisionLayer:"Managerial campaign decision",applyCampaignRule:"Apply a campaign threshold to the model probability",campaignThreshold:"What-if threshold",decisionLayerNote:"The model probability never changes when you adjust this rule. Turn it off to view the model output without a campaign decision. A 0% threshold is still an active, very strict rule.",modelOutput:"Model output: return probability",modelOnlyNote:"This probability is the model result. A Yes/No campaign choice requires a separate decision rule.",campaignDecision:"What-if campaign decision",ruleOff:"Not applied",ruleOffNote:"Campaign rule off: only the model probability is shown. No campaign eligibility decision is made.",ruleYes:"Yes — review for outreach",ruleNo:"No — do not target",decisionAtOrBelow:"{probability} is at or below your {threshold} what-if threshold. This rule would flag the profile for human campaign review; it does not contact anyone.",decisionAbove:"{probability} is above your {threshold} what-if threshold. This rule would not flag the profile for outreach. The model probability is unchanged.",thresholdForModelNote:"The original 40% threshold was selected for the temporal model. Any slider setting is a local what-if decision, not an approved policy change."});
Object.assign(words.fr,{decisionLayer:"Décision de campagne de la direction",applyCampaignRule:"Appliquer un seuil de campagne à la probabilité du modèle",campaignThreshold:"Seuil hypothétique",decisionLayerNote:"La probabilité du modèle ne change jamais lorsque vous ajustez cette règle. Désactivez-la pour voir le résultat du modèle sans décision de campagne. Un seuil de 0 % reste une règle active très stricte.",modelOutput:"Résultat du modèle : probabilité de retour",modelOnlyNote:"Cette probabilité est le résultat du modèle. Une décision de campagne Oui/Non exige une règle distincte.",campaignDecision:"Décision de campagne hypothétique",ruleOff:"Non appliquée",ruleOffNote:"Règle de campagne désactivée : seule la probabilité du modèle est affichée. Aucune décision d'admissibilité à la campagne n'est prise.",ruleYes:"Oui — examiner pour une intervention",ruleNo:"Non — ne pas cibler",decisionAtOrBelow:"{probability} est inférieur ou égal à votre seuil hypothétique de {threshold}. Cette règle signalerait le profil pour examen humain; elle ne contacte personne.",decisionAbove:"{probability} dépasse votre seuil hypothétique de {threshold}. Cette règle ne signalerait pas le profil pour une intervention. La probabilité du modèle ne change pas.",thresholdForModelNote:"Le seuil initial de 40 % a été choisi pour le modèle temporel. Toute valeur du curseur est une décision hypothétique locale, pas une modification approuvée de la politique."});
Object.assign(words.en,{faqCategoryLabel:"Question category",faqQuestionLabel:"Common question",faqHelp:"Choose a common question to fill the box, or select Ask another question and write your own.",faqChooseCategory:"Choose a category",faqChooseQuestion:"Choose a common question",faqCustom:"Ask another question",faqReturns:"Returns and refunds",faqShipping:"Shipping and delivery",faqLoyalty:"Loyalty and retention offers",faqPrivacy:"Privacy and customer data",faqProducts:"Product information",faqRecommendations:"Recommendations",faqRetention:"Retention support"});
Object.assign(words.fr,{faqCategoryLabel:"Catégorie de question",faqQuestionLabel:"Question fréquente",faqHelp:"Choisissez une question fréquente pour remplir la zone, ou sélectionnez Poser une autre question et écrivez la vôtre.",faqChooseCategory:"Choisir une catégorie",faqChooseQuestion:"Choisir une question fréquente",faqCustom:"Poser une autre question",faqReturns:"Retours et remboursements",faqShipping:"Expédition et livraison",faqLoyalty:"Fidélité et offres de rétention",faqPrivacy:"Confidentialité et données client",faqProducts:"Renseignements sur les produits",faqRecommendations:"Recommandations",faqRetention:"Soutien à la fidélisation"});
Object.assign(words.en,{questionModeLabel:"Question entry mode",questionModeFaq:"Browse FAQs",questionModeCustom:"Ask my own question",faqHelp:"Choose a common question to fill the box, or choose Ask my own question to write yours."});
Object.assign(words.fr,{questionModeLabel:"Mode de saisie de la question",questionModeFaq:"Parcourir les FAQ",questionModeCustom:"Poser ma propre question",faqHelp:"Choisissez une question fréquente pour remplir la zone, ou choisissez Poser ma propre question pour écrire la vôtre."});
const faqCategories = [
  {id:"returns",label:"faqReturns"},{id:"shipping",label:"faqShipping"},{id:"privacy",label:"faqPrivacy"}
];
const faqQuestions = [
  {id:"returns-window",category:"returns",en:"How many days do I have to return an item?",fr:"Combien de jours ai-je pour retourner un article?"},
  {id:"returns-exclusions",category:"returns",en:"Which products cannot be returned?",fr:"Quels produits ne peuvent pas être retournés?"},
  {id:"returns-refund",category:"returns",en:"How long does an approved refund take?",fr:"Combien de temps faut-il pour recevoir un remboursement approuvé?"},
  {id:"shipping-time",category:"shipping",en:"What are the estimated delivery times?",fr:"Quels sont les délais de livraison estimés?"},
  {id:"shipping-address",category:"shipping",en:"Can I change my delivery address after fulfillment begins?",fr:"Puis-je modifier mon adresse de livraison après le début de la préparation?"},
  {id:"shipping-tracking",category:"shipping",en:"When does the carrier provide parcel tracking after dispatch?",fr:"Quand le transporteur fournit-il le suivi du colis après l'expédition?"},
  {id:"privacy-access",category:"privacy",en:"What customer information may staff access for a service request?",fr:"Quels renseignements sur un client le personnel peut-il consulter pour une demande de service?"},
  {id:"privacy-identity",category:"privacy",en:"Why must identity be verified before discussing account-specific information?",fr:"Pourquoi l'identité doit-elle être vérifiée avant de discuter des renseignements d'un compte?"}
];
Object.assign(words.en,{assistantIntro:"Choose the customer or staff path. Product search and recommendations use the demonstration catalog; staff retention guidance requires internal access.",customerAssistantTitle:"Customer assistant",customerAssistantNote:"Search the demonstration catalog by product name or code, ask for recommendations, or browse customer policies. Recommendations can use your Head B basket. This is not live stock availability.",assistantTaskLabel:"What would you like to do?",assistantTaskAuto:"Let the assistant identify my question",assistantTaskLookup:"Find a product by name or code",assistantTaskRecommend:"Get product recommendations",assistantTaskPolicy:"Ask about a customer policy",staffAssistantTitle:"Internal staff · retention and loyalty",staffAssistantNote:"For authorized staff only. Answers use the internal demonstration policy; no customer-specific score, offer approval, or identity verification is performed here.",staffTokenLabel:"Internal API token",staffQuestionLabel:"Retention or loyalty question",staffQuestionPlaceholder:"Are retention offers guaranteed?",staffAskButton:"Ask staff assistant",staffAssistantWaiting:"Internal guidance and source will appear here after authorization.",catalogMatch:"Matching demonstration products",noCatalogMatch:"No matching products in the demonstration catalog.",recommendedProducts:"Suggested products",fromProduct:"Based on",fromBasket:"Based on the current basket",generalPopularity:"General popularity fallback (not personalized)",staffAuthError:"Staff access requires a configured internal token."});
Object.assign(words.fr,{assistantIntro:"Choisissez l'accès client ou personnel. La recherche et les recommandations utilisent le catalogue de démonstration; les conseils internes exigent une autorisation.",customerAssistantTitle:"Assistant clientèle",customerAssistantNote:"Cherchez un produit par nom ou code, demandez des recommandations ou consultez les politiques destinées aux clients. Les recommandations peuvent utiliser votre panier de Head B. Ce catalogue ne confirme pas les stocks en temps réel.",assistantTaskLabel:"Que souhaitez-vous faire?",assistantTaskAuto:"Laisser l'assistant reconnaître la question",assistantTaskLookup:"Trouver un produit par nom ou code",assistantTaskRecommend:"Obtenir des recommandations",assistantTaskPolicy:"Consulter une politique client",staffAssistantTitle:"Personnel interne · fidélisation et loyauté",staffAssistantNote:"Réservé au personnel autorisé. Les réponses proviennent de la politique interne fictive; aucun score individuel, approbation d'offre ou contrôle d'identité n'est effectué ici.",staffTokenLabel:"Jeton API interne",staffQuestionLabel:"Question sur la fidélisation ou la loyauté",staffQuestionPlaceholder:"Les offres de fidélisation sont-elles garanties?",staffAskButton:"Consulter l'assistant interne",staffAssistantWaiting:"Les conseils internes et leur source apparaîtront ici après autorisation.",catalogMatch:"Produits correspondants du catalogue de démonstration",noCatalogMatch:"Aucun produit correspondant dans le catalogue de démonstration.",recommendedProducts:"Produits suggérés",fromProduct:"À partir de",fromBasket:"À partir du panier actuel",generalPopularity:"Produits populaires en général (non personnalisés)",staffAuthError:"Un jeton interne configuré est nécessaire."});
Object.assign(words.en,{staffAssistantNote:"Demo staff sign-in only. Answers use the internal demonstration policy; no customer-specific score or offer approval is performed here.",staffUsernameLabel:"Demo username",staffPasswordLabel:"Demo password",staffSignInButton:"Sign in to staff demo",staffSignOutButton:"Sign out",staffSignedIn:"Signed in to staff demo",staffSignInFailed:"Staff sign-in failed",staffSessionExpired:"Staff session expired. Please sign in again."});
Object.assign(words.fr,{staffAssistantNote:"Connexion du personnel fictif pour la démonstration seulement. Les réponses proviennent de la politique interne; aucun score individuel ni approbation d'offre n'est effectué ici.",staffUsernameLabel:"Nom d'utilisateur fictif",staffPasswordLabel:"Mot de passe fictif",staffSignInButton:"Ouvrir une session du personnel",staffSignOutButton:"Fermer la session",staffSignedIn:"Session du personnel ouverte",staffSignInFailed:"Échec de la connexion du personnel",staffSessionExpired:"La session du personnel a expiré. Veuillez vous reconnecter."});
Object.assign(words.en,{assistantProviderLabel:"Question-routing provider",assistantProviderBaseline:"Rule / keyword baseline",assistantProviderOpenAI:"Hosted OpenAI",assistantProviderOllama:"Local Ollama",assistantHostedConsent:"I confirm this question contains no personal or customer data and may be sent to OpenAI.",providerBaselineNote:"Uses local rules and grounded tools; no LLM call.",providerOpenAINote:"OpenAI classifies the question; approved local tools supply the answer. The question is sent to OpenAI and may incur API cost.",providerOllamaNote:"Ollama classifies the question; approved local tools supply the answer. Requires a configured private Ollama service.",providerUnavailable:"Not configured on this server.",providerResult:"Routing provider"});
Object.assign(words.fr,{assistantProviderLabel:"Fournisseur de classification des questions",assistantProviderBaseline:"Règles / mots-clés",assistantProviderOpenAI:"OpenAI hébergé",assistantProviderOllama:"Ollama local",assistantHostedConsent:"Je confirme que cette question ne contient aucune donnée personnelle ou client et qu'elle peut être envoyée à OpenAI.",providerBaselineNote:"Utilise des règles et des outils locaux; aucun appel à un LLM.",providerOpenAINote:"OpenAI classe la question; les outils locaux approuvés fournissent la réponse. La question est envoyée à OpenAI et peut entraîner des frais.",providerOllamaNote:"Ollama classe la question; les outils locaux approuvés fournissent la réponse. Un service Ollama privé configuré est requis.",providerUnavailable:"Non configuré sur ce serveur.",providerResult:"Fournisseur de classification"});
Object.assign(words.en,{assistantProviderHuggingFace:"Hugging Face Inference Providers",assistantHostedConsent:"I confirm this question contains no personal or customer data and may be sent to the selected hosted provider.",providerHuggingFaceNote:"Hugging Face classifies the question; approved local tools supply the answer. The question is sent to Hugging Face and may incur usage charges.",providerNote:"Only configured providers can be selected. LLMs route the question; approved local tools provide the answer and citations. No free-form LLM answer is presented."});
Object.assign(words.fr,{assistantProviderHuggingFace:"Fournisseurs d'inférence Hugging Face",assistantHostedConsent:"Je confirme que cette question ne contient aucune donnée personnelle ou client et qu'elle peut être envoyée au fournisseur hébergé sélectionné.",providerHuggingFaceNote:"Hugging Face classe la question; les outils locaux approuvés fournissent la réponse. La question est envoyée à Hugging Face et peut entraîner des frais.",providerNote:"Seuls les fournisseurs configurés peuvent être sélectionnés. Les LLM classent la question; les outils locaux approuvés fournissent la réponse et les sources. Aucune réponse libre du LLM n'est présentée."});
Object.assign(words.en,{providerAccessLabel:"LLM demo access token"});
Object.assign(words.fr,{providerAccessLabel:"Jeton d'accès à la démonstration LLM"});
Object.assign(words.en,{driftTitle:"Synthetic distribution-shift comparison",driftIntro:"Separate from API errors: compare valid fictional profiles with aggregate train/validation distributions. Profiles are not saved or added to training data.",driftReferenceButton:"Compare reference-like batch",driftShiftedButton:"Compare shifted batch",driftWaiting:"Synthetic drift comparison is not enabled on this server.",driftReady:"Development-only aggregate baseline ready · 100 fictional profiles per comparison.",driftUnavailable:"Synthetic drift demonstration is disabled on this server.",driftRunning:"Comparing 100 valid fictional profiles…",driftFailed:"Drift comparison failed",driftStatus:"Input drift",driftScoreStatus:"Score distribution",driftIndicator:"Indicator",driftMetric:"Monitored measure",driftPsi:"PSI",driftRange:"Outside development range",driftSamples:"Profiles",driftStable:"Stable",driftWatch:"Watch",driftHigh:"High shift",driftInsufficient:"Insufficient samples",driftScore:"Return probability",driftCaution:"Illustrative PSI thresholds; not an automatic retraining decision. Score shift is shown separately: synthetic feature combinations can score differently even when four input distributions match. The score reference uses development rows and is not a performance estimate. This is not the API-error alert."});
Object.assign(words.fr,{driftTitle:"Comparaison de distributions fictives",driftIntro:"Distincte des erreurs API : comparer des profils fictifs valides aux distributions agrégées d'entraînement et de validation. Les profils ne sont ni enregistrés ni ajoutés aux données d'entraînement.",driftReferenceButton:"Comparer un lot de référence",driftShiftedButton:"Comparer un lot modifié",driftWaiting:"La comparaison de dérive fictive n'est pas activée sur ce serveur.",driftReady:"Référence agrégée de développement prête · 100 profils fictifs par comparaison.",driftUnavailable:"La démonstration de dérive fictive est désactivée sur ce serveur.",driftRunning:"Comparaison de 100 profils fictifs valides…",driftFailed:"Échec de la comparaison",driftStatus:"Dérive des entrées",driftScoreStatus:"Distribution des scores",driftIndicator:"Indicateur",driftMetric:"Mesure surveillée",driftPsi:"PSI",driftRange:"Hors plage de développement",driftSamples:"Profils",driftStable:"Stable",driftWatch:"À surveiller",driftHigh:"Forte variation",driftInsufficient:"Échantillon insuffisant",driftScore:"Probabilité de retour",driftCaution:"Seuils PSI illustratifs; aucune décision automatique de réentraînement. La variation des scores est affichée séparément : des combinaisons fictives peuvent produire des scores différents même si les quatre distributions d'entrée correspondent. La référence des scores provient des données de développement et n'est pas une mesure de performance. Ceci n'est pas l'alerte d'erreurs API."});
let language = localStorage.getItem("boreal-language") === "fr" ? "fr" : "en";
const t = (key) => words[language][key] || words.en[key] || key;
let contract, features, searchTimer, predictionId = 0, searchId = 0, catalogTotal = 0, readyState, lastPrediction = null;
let catalogOffset = 0, categoryCounts = {};
const catalogPageSize = 18;
let basket = [];
try { const saved = JSON.parse(localStorage.getItem("boreal-basket") || "[]"); if (Array.isArray(saved)) basket = saved.filter((item) => typeof item === "string").slice(0, 50); } catch (_) { /* ignore malformed browser state */ }
const descriptions = new Map();
let catalogItems = [], lastRecommendation = null, lastAssistantResult = null, lastStaffResult = null, selectedFaqId = "", questionMode = "faq";
let driftReference = null, lastDriftResult = null;
async function api(path, options = {}) {
  const {headers = {}, ...rest} = options;
  const response = await fetch(path, {credentials:"same-origin",...rest,headers:{"Content-Type":"application/json",...headers}});
  const payload = await response.json().catch(() => ({detail:"Non-JSON response"}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  return payload;
}
function show(element, html, error = false) { element.className = `result${error ? " error" : ""}`; element.innerHTML = html; }
function renderFaqControls() {
  const category = $("#faq-category");
  const question = $("#faq-question");
  const activeCategory = category.value;
  category.innerHTML = `<option value="">${safe(t("faqChooseCategory"))}</option>${faqCategories.map((item) => `<option value="${item.id}">${safe(t(item.label))}</option>`).join("")}`;
  category.value = activeCategory;
  const matches = faqQuestions.filter((item) => !activeCategory || item.category === activeCategory);
  question.innerHTML = `<option value="">${safe(t("faqChooseQuestion"))}</option>${matches.map((item) => `<option value="${item.id}">${safe(item[language])}</option>`).join("")}`;
  question.value = matches.some((item) => item.id === selectedFaqId) ? selectedFaqId : "";
  if (question.value && question.value !== "custom") $("#question").value = faqQuestions.find((item) => item.id === question.value)[language];
}
function setQuestionMode(mode) {
  questionMode = mode;
  const custom = mode === "custom";
  $("#faq-picker").hidden = custom;
  $("#faq-help").hidden = custom;
  for (const value of ["faq", "custom"]) {
    const button = $(`#question-mode-${value}`);
    button.classList.toggle("selected", value === mode);
    button.setAttribute("aria-pressed", String(value === mode));
  }
  if (custom) {
    selectedFaqId = "";
    $("#faq-question").value = "";
    $("#question").value = "";
    $("#assistant-task").value = "auto";
    $("#question").focus();
  }
}
function orderBilingualAnswer(value) {
  const lines = String(value).replaceAll("\r\n", "\n").split("\n");
  const headings = lines.map((line, index) => {
    const match = line.trim().match(/^##\s*(English|Français)\s*$/i);
    return match ? {index, code: match[1].toLowerCase() === "english" ? "en" : "fr"} : null;
  }).filter(Boolean);
  if (!headings.some((item) => item.code === "en") || !headings.some((item) => item.code === "fr")) return lines.join("\n");
  const sections = {};
  headings.forEach((heading, position) => {
    const end = position + 1 < headings.length ? headings[position + 1].index : lines.length;
    sections[heading.code] = lines.slice(heading.index, end).join("\n").trim();
  });
  const preferred = language === "fr" ? ["fr", "en"] : ["en", "fr"];
  return preferred.map((code) => sections[code]).filter(Boolean).join("\n\n");
}
function renderAssistant(result, target = "#assistant-result") {
  const citations = result.citations.length ? `<p><small>${t("sources")}: ${result.citations.map((item) => `${safe(item.title)} (${safe(item.version)})`).join("; ")}</small></p>` : "";
  const answer = orderBilingualAnswer(result.answer).split("\n").map((line) => line.startsWith("## ")?`<strong class="answer-heading">${safe(line.slice(3))}</strong>`:safe(line)).join("<br>");
  const tools = result.tool_result || {};
  let details = "";
  if (result.intent === "product_lookup") {
    const products = tools.products || [];
    details = products.length ? `<h4>${t("catalogMatch")}</h4><ul class="assistant-products">${products.map((item) => `<li><strong>${safe(item.description)}</strong><small>${safe(item.stock_code)}</small></li>`).join("")}</ul>` : `<p>${t("noCatalogMatch")}</p>`;
  } else if (result.intent === "recommendation") {
    const products = tools.recommendations || [];
    const basis = tools.matched_product ? `${t("fromProduct")}: ${safe(tools.matched_product.description)}` : (tools.used_basket || []).length ? t("fromBasket") : t("generalPopularity");
    details = `<h4>${t("recommendedProducts")}</h4><p class="footnote">${basis}</p><ul class="assistant-products">${products.map((item) => `<li><strong>${safe((tools.product_descriptions || {})[item.item] || item.item)}</strong><small>${safe(item.item)}</small></li>`).join("")}</ul>`;
  }
  const provider = result.provider || "baseline";
  show($(target), `<p><strong>${safe(result.intent.replaceAll("_"," "))}</strong> · ${result.refused?t("refused"):result.handoff?t("handoff"):t("answered")}<br><small>${t("providerResult")}: ${safe(provider)}${result.model ? ` · ${safe(result.model)}` : ""}</small></p><p>${answer}</p>${details}${citations}`);
}
function setStaffSignedIn(authenticated) {
  $("#staff-login-form").hidden = authenticated;
  $("#staff-session-controls").hidden = !authenticated;
  $("#staff-assistant-form").hidden = !authenticated;
  if (!authenticated) {
    lastStaffResult = null;
    show($("#staff-assistant-result"), safe(t("staffAssistantWaiting")));
    $("#staff-assistant-result").classList.add("empty");
  }
}
function updateAssistantProvider() {
  const provider = $("#assistant-provider").value;
  $("#assistant-provider-note").textContent = t(provider === "openai" ? "providerOpenAINote" : provider === "huggingface" ? "providerHuggingFaceNote" : provider === "ollama" ? "providerOllamaNote" : "providerBaselineNote");
  $("#hosted-consent-row").hidden = !["openai","huggingface"].includes(provider);
  $("#provider-access-row").hidden = provider === "baseline";
  $("#assistant-task").disabled = provider !== "baseline";
  if (provider !== "baseline") $("#assistant-task").value = "auto";
}
function setLanguage(value) {
  language = value; localStorage.setItem("boreal-language", value); document.documentElement.lang = value;
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => { element.placeholder = t(element.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => { element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel)); });
  for (const code of ["en","fr"]) { const button = $(`#lang-${code}`); button.classList.toggle("selected", code === value); button.setAttribute("aria-pressed", String(code === value)); }
  if (readyState !== undefined) $("#health-label").textContent = readyState ? t("ready") : t("degraded");
  renderCategoryOptions(); renderCatalogMeta();
  renderBasket(); renderCatalog(); if (lastRecommendation) renderRecommendations(lastRecommendation);
  if (lastPrediction) renderPrediction(lastPrediction); else if (features) markPredictionPending($("#scenario").value === "custom");
  $("#model-method-note").textContent = t($("#retention-model").value === "random_80_20" ? "randomNote" : "temporalNote");
  if (lastAssistantResult) renderAssistant(lastAssistantResult);
  if (lastStaffResult) renderAssistant(lastStaffResult,"#staff-assistant-result");
  renderFaqControls();
  updateAssistantProvider();
  if (lastDriftResult) renderDrift(lastDriftResult);
  if (driftReference) $("#drift-reference-status").textContent = t("driftReady");
  refreshMetrics();
}
$("#lang-en").addEventListener("click", () => setLanguage("en"));
$("#lang-fr").addEventListener("click", () => setLanguage("fr"));
$("#assistant-provider").addEventListener("change", updateAssistantProvider);
$("#question-mode-faq").addEventListener("click", () => setQuestionMode("faq"));
$("#question-mode-custom").addEventListener("click", () => setQuestionMode("custom"));
$("#faq-category").addEventListener("change", () => { selectedFaqId = ""; renderFaqControls(); });
$("#faq-question").addEventListener("change", (event) => {
  selectedFaqId = event.target.value;
  const selected = faqQuestions.find((item) => item.id === selectedFaqId);
  if (selected) { $("#question").value = selected[language]; if ($("#assistant-provider").value === "baseline") $("#assistant-task").value = "policy_search"; }
});
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab,.panel").forEach((element) => element.classList.remove("active"));
  tab.classList.add("active"); $(`#${tab.dataset.panel}`).classList.add("active");
}));
const scenarios = {
  starter:{recency_days:30,frequency_orders:3,monetary_total:150,unique_products:12},
  frequent:{recency_days:7,frequency_orders:18,monetary_total:1800,unique_products:55},
  lapsed:{recency_days:180,frequency_orders:2,monetary_total:75,unique_products:6},
  likelyReturn:{recency_days:20,frequency_orders:6,monetary_total:800,unique_products:30}
};
const sliders = [["recency_days","recency-slider","recency-value"],["frequency_orders","frequency-slider","frequency-value"],["monetary_total","spend-slider","spend-value"],["unique_products","products-slider","products-value"]];
$("#retention-model").addEventListener("change", () => { $("#model-method-note").textContent=t($("#retention-model").value === "random_80_20" ? "randomNote" : "temporalNote"); markPredictionPending($("#scenario").value === "custom"); });
function coherentRetentionProfile(source) {
  const profile = {...source};
  const observationDays = 365.25;
  const recency = Math.max(0,Number(profile.recency_days)||0);
  const orders = Math.max(1,Number(profile.frequency_orders)||1);
  const spend = Math.max(25,Number(profile.monetary_total)||25);
  const products = Math.max(1,Number(profile.unique_products)||1);
  const activeSpan = Math.max(0,observationDays-recency);
  const lines = Math.max(products,Math.round(products*1.4));
  const quantity = Math.max(products,Math.round(lines*2.5));
  const orderValue = spend/orders;
  const price = spend/Math.max(quantity,1);
  Object.assign(profile,{
    recency_days:recency,frequency_orders:orders,monetary_total:spend,unique_products:products,
    quantity_total:quantity,line_count:lines,country_count:1,
    unit_price_mean:price,unit_price_median:price*.75,unit_price_max:price*3,
    order_value_mean:orderValue,order_value_median:orderValue*.9,order_value_std:orderValue*.35,order_value_max:orderValue*1.8,
    basket_lines_mean:lines/orders,basket_lines_median:Math.max(1,Math.round(lines/orders)),basket_lines_max:Math.max(1,Math.round(lines/orders*1.8)),
    basket_unique_products_mean:Math.min(products,Math.max(1,products/orders)),basket_quantity_mean:quantity/orders,
    tenure_days:observationDays,active_span_days:activeSpan,monthly_order_frequency:orders/(observationDays/30.4375),
    quantity_per_order:quantity/orders,product_diversity_ratio:products/Math.max(lines,1),order_value_cv:.35,
    repeat_product_ratio:Math.max(0,Math.min(1,1-products/Math.max(quantity,1)))
  });
  if (orders>1 && activeSpan>0) {
    profile.cadence_days_mean=activeSpan/(orders-1);
    profile.cadence_days_std=profile.cadence_days_mean*.35;
    profile.recency_to_cadence=recency/profile.cadence_days_mean;
  } else {
    profile.cadence_days_mean=null; profile.cadence_days_std=null; profile.recency_to_cadence=null;
  }
  for (const days of [30,60,90]) {
    const recentOrders=recency>days?0:Math.min(orders,Math.max(1,Math.round(orders*days/observationDays)));
    const share=recentOrders/orders;
    profile[`recent_${days}d_orders`]=recentOrders;
    profile[`recent_${days}d_lines`]=Math.round(lines*share);
    if (days===90) profile.recent_90d_spend=spend*share;
  }
  profile.primary_country=String(profile.primary_country||"UNITED KINGDOM").trim().toUpperCase();
  return profile;
}
function syncSliders() { for (const [field,input,output] of sliders) { $(`#${input}`).value = Number(features[field] || 0); $(`#${output}`).value = Number(features[field] || 0).toLocaleString(language); } $("#feature-json").value = JSON.stringify(features,null,2); }
function markPredictionPending(custom = false) { lastPrediction = null; $("#prediction-result").className = "result empty"; $("#prediction-result").textContent = t(custom ? "predictionChanged" : "predictionReady"); }
function loadScenario() { if (!contract || $("#scenario").value === "custom") return; features = coherentRetentionProfile({...contract.synthetic_example,...scenarios[$("#scenario").value]}); syncSliders(); markPredictionPending(false); }
$("#scenario").addEventListener("change", loadScenario);
$("#load-example").addEventListener("click", () => { if ($("#scenario").value === "custom") $("#scenario").value = "starter"; loadScenario(); });
for (const [field,input] of sliders) $(`#${input}`).addEventListener("input", () => { if (!features) return; features[field] = Number($(`#${input}`).value); features = coherentRetentionProfile(features); $("#scenario").value = "custom"; syncSliders(); markPredictionPending(true); });
function syncCampaignControls() {
  const enabled = $("#apply-campaign-rule").checked;
  $("#campaign-threshold").disabled = !enabled;
  $(".campaign-controls").classList.toggle("inactive", !enabled);
  $("#campaign-threshold-value").textContent = `${$("#campaign-threshold").value}%`;
  if (lastPrediction) renderPrediction(lastPrediction);
}
$("#apply-campaign-rule").addEventListener("change", syncCampaignControls);
$("#campaign-threshold").addEventListener("input", syncCampaignControls);
syncCampaignControls();
$("#toggle-advanced").addEventListener("click", () => { const expanded = $("#toggle-advanced").getAttribute("aria-expanded") === "true"; $("#toggle-advanced").setAttribute("aria-expanded", String(!expanded)); $("#advanced-inputs").hidden = expanded; });
function renderPrediction(result) {
  const probability=`${(result.return_probability_90d*100).toFixed(1)}%`;
  const enabled=$("#apply-campaign-rule").checked;
  const threshold=Number($("#campaign-threshold").value)/100;
  const thresholdLabel=`${(threshold*100).toFixed(0)}%`;
  const decision=result.return_probability_90d<=threshold;
  const explanation=enabled ? t(decision?"decisionAtOrBelow":"decisionAbove").replace("{probability}",probability).replace("{threshold}",thresholdLabel) : t("ruleOffNote");
  const variant=result.model_variant === "random_80_20" ? "randomModel" : "temporalModel";
  const winner=result.model_variant === "random_80_20" && contract?.random_split_winner ? ` · ${t("winningFamily")}: ${safe(contract.random_split_winner.replaceAll("_"," "))}` : "";
  const decisionPanel=enabled ? `<h3>${t("decisionLayer")}</h3><div class="result-grid"><article><small>${t("campaignThreshold")}</small><strong>${thresholdLabel}</strong></article><article><small>${t("campaignDecision")}</small><strong>${t(decision?"ruleYes":"ruleNo")}</strong></article></div>` : `<h3>${t("decisionLayer")}</h3><p><strong>${t("ruleOff")}</strong></p>`;
  show($("#prediction-result"), `<p><strong>${t("modelUsed")}:</strong> ${t(variant)}${winner}</p><div class="result-grid"><article><small>${t("modelOutput")}</small><strong>${probability}</strong></article><article><small>${t("version")}</small><strong>${safe(result.model_version)}</strong></article></div><p class="footnote">${t("modelOnlyNote")}</p><div class="decision-output">${decisionPanel}<p class="prediction-explanation">${safe(explanation)}</p><p class="footnote">${t("thresholdForModelNote")}</p></div>${result.model_variant === "random_80_20" ? `<p class="footnote">${t("randomResultNote")}</p>` : ""}`);
}
async function runPrediction() {
  const current = ++predictionId; $("#prediction-result").className = "result empty"; $("#prediction-result").textContent = t("updating");
  try { const result = await api("/predict",{method:"POST",body:JSON.stringify({features,model_variant:$("#retention-model").value})}); if (current !== predictionId) return; lastPrediction = result; renderPrediction(result); }
  catch (error) { if (current === predictionId) show($("#prediction-result"), `<strong>${t("predictionFailed")}</strong><br>${safe(error.message)}`,true); }
}
$("#predict-button").addEventListener("click",runPrediction);
function renderBasket() {
  $("#basket-count").textContent = `${basket.length} ${t(basket.length === 1 ? "item" : "items")}`;
  $("#basket-items").innerHTML = basket.length ? basket.map((code,index) => `<div class="basket-line"><span class="basket-index">${index+1}</span><span><strong>${safe(descriptions.get(code)||code)}</strong><small>${safe(code)}</small></span><button type="button" data-remove="${safe(code)}" aria-label="${t("remove")} ${safe(code)}">×</button></div>`).join("") : `<p class="footnote">${t("basketEmpty")}</p>`;
}
const categoryTranslationKeys = {kitchen_dining:"categoryKitchenDining",bags_storage:"categoryBagsStorage",stationery_crafts:"categoryStationeryCrafts",home_decor:"categoryHomeDecor",gifts_seasonal:"categoryGiftsSeasonal",accessories:"categoryAccessories",other:"categoryOther"};
function formatText(key, values) { return Object.entries(values).reduce((text,[name,value]) => text.replace(`{${name}}`,value),t(key)); }
function renderCategoryOptions() {
  const select = $("#category-filter");
  const selected = select.value || "all";
  select.innerHTML = `<option value="all">${t("categoryAll")} (${Object.values(categoryCounts).reduce((sum,count) => sum+count,0) || 300})</option>` + Object.entries(categoryCounts).map(([category,count]) => `<option value="${safe(category)}">${safe(t(categoryTranslationKeys[category] || "categoryOther"))} (${count})</option>`).join("");
  select.value = [...select.options].some((option) => option.value === selected) ? selected : "all";
}
function renderCatalogMeta() {
  const start = catalogTotal ? catalogOffset + 1 : 0;
  const end = Math.min(catalogOffset + catalogItems.length,catalogTotal);
  const pages = Math.max(1,Math.ceil(catalogTotal/catalogPageSize));
  const page = Math.min(pages,Math.floor(catalogOffset/catalogPageSize)+1);
  $("#catalog-status").textContent = formatText("showingRange",{start,end,total:catalogTotal});
  $("#catalog-page").textContent = formatText("pageOf",{page,pages});
  $("#catalog-prev").disabled = catalogOffset === 0;
  $("#catalog-next").disabled = catalogOffset + catalogItems.length >= catalogTotal;
}
function renderCatalog() { $("#catalog-results").innerHTML = catalogItems.length ? catalogItems.map((item) => `<article class="product-card"><div><strong>${safe(item.description)}</strong><small>${safe(item.stock_code)} · ${safe(t(categoryTranslationKeys[item.category] || "categoryOther"))}</small></div><button type="button" data-add="${safe(item.stock_code)}" ${basket.includes(item.stock_code)?"disabled":""}>${basket.includes(item.stock_code)?"✓":t("add")}</button></article>`).join("") : `<p class="footnote">${t("noProducts")}</p>`; }
async function hydrateBasketDescriptions() {
  await Promise.all(basket.filter((code) => !descriptions.has(code)).map(async (code) => {
    try {
      const result = await api(`/catalog?q=${encodeURIComponent(code)}&limit=5`);
      const product = result.items.find((item) => item.stock_code === code);
      if (product) descriptions.set(code,product.description);
    } catch (_) { /* keep the traceable product code if catalog lookup is unavailable */ }
  }));
  renderBasket();
}
async function searchCatalog() {
  const current = ++searchId;
  const category = $("#category-filter").value || "all";
  try { const result = await api(`/catalog?q=${encodeURIComponent($("#product-search").value.trim())}&category=${encodeURIComponent(category)}&offset=${catalogOffset}&limit=${catalogPageSize}`); if (current !== searchId) return;
    catalogItems = result.items; catalogTotal = result.total; categoryCounts = result.categories; for (const item of result.items) descriptions.set(item.stock_code,item.description);
    renderCategoryOptions(); renderCatalogMeta(); renderCatalog(); renderBasket();
  } catch (error) { if (current === searchId) $("#catalog-status").textContent = `${t("searchFailed")}: ${error.message}`; }
}
$("#product-search").addEventListener("input", () => { catalogOffset = 0; clearTimeout(searchTimer); searchTimer = setTimeout(searchCatalog,200); });
$("#category-filter").addEventListener("change", () => { catalogOffset = 0; searchCatalog(); });
$("#clear-search").addEventListener("click", () => { $("#product-search").value = ""; $("#category-filter").value = "all"; catalogOffset = 0; searchCatalog(); $("#product-search").focus(); });
$("#catalog-prev").addEventListener("click", () => { catalogOffset = Math.max(0,catalogOffset-catalogPageSize); searchCatalog(); $("#catalog-results").scrollTop = 0; });
$("#catalog-next").addEventListener("click", () => { if (catalogOffset+catalogPageSize < catalogTotal) catalogOffset += catalogPageSize; searchCatalog(); $("#catalog-results").scrollTop = 0; });
$("#catalog-results").addEventListener("click", (event) => { const code = event.target.closest("[data-add]")?.dataset.add; if (!code || basket.includes(code) || basket.length >= 50) return; basket.push(code); localStorage.setItem("boreal-basket",JSON.stringify(basket)); renderBasket(); renderCatalog(); getRecommendations(); });
$("#basket-items").addEventListener("click", (event) => { const code = event.target.closest("[data-remove]")?.dataset.remove; if (!code) return; basket = basket.filter((item) => item !== code); localStorage.setItem("boreal-basket",JSON.stringify(basket)); renderBasket(); renderCatalog(); getRecommendations(); });
$("#clear-basket").addEventListener("click", () => { basket = []; localStorage.setItem("boreal-basket","[]"); renderBasket(); renderCatalog(); getRecommendations(); });
$("#recommend-button").addEventListener("click", getRecommendations);
$("#continue-to-basket").addEventListener("click", async () => {
  const code = "15056BL";
  try {
    const result = await api(`/catalog?q=${encodeURIComponent(code)}&limit=1`);
    const product = result.items.find((item) => item.stock_code === code);
    if (!product) throw new Error("Example product unavailable");
    descriptions.set(code, product.description); basket = [code]; localStorage.setItem("boreal-basket",JSON.stringify(basket));
    $("#product-search").value = ""; $("#category-filter").value = "all"; catalogOffset = 0;
    document.querySelector('.tab[data-panel="recommendations"]').click();
    $("#journey-notice").hidden = false; renderBasket(); await searchCatalog(); await getRecommendations();
    $("#recommendations").scrollIntoView({behavior:"smooth",block:"start"});
  } catch (error) { show($("#prediction-result"), `<strong>${t("journeyFailed")}</strong><br>${safe(error.message)}`,true); }
});
function ruleReason(rule) { if (!rule) return t("itemFallback"); const codes = rule.split("->")[0]?.replace(/[()'\[\]]/g,"").split(",").map((code) => code.trim()).filter(Boolean) || []; return `${t("because")} ${codes.map((code) => safe(descriptions.get(code)||code)).join(", ")}`; }
function renderRecommendations(result) {
  const source = result.source === "association_rules" ? t("rules") : result.source === "empty_basket_popularity" ? t("emptyFallback") : t("noMatchFallback");
  const cards = result.recommendations.map((item) => `<article class="recommend-card"><div><strong>${safe(descriptions.get(item.item)||item.item)}</strong><small>${safe(item.item)}</small><p>${ruleReason(item.firing_rule)}</p></div>${item.confidence == null?"":`<small>Confidence ${(item.confidence*100).toFixed(0)}% · Lift ${item.lift?.toFixed(2)??"—"}</small>`}</article>`).join("");
  show($("#recommend-result"), `<strong>${safe(source)}</strong>${result.source === "association_rules"?"":`<p>${t("fallbackExplanation")}</p>`}<div class="recommend-list">${cards||`<p>${t("noRecommendations")}</p>`}</div>`);
}
async function getRecommendations() {
  try { const result = await api("/recommend",{method:"POST",body:JSON.stringify({basket,k:Number($("#recommend-k").value)})}); lastRecommendation = result;
    const missing = result.recommendations.map((item) => item.item).filter((code) => !descriptions.has(code));
    await Promise.all(missing.map(async (code) => { const found = await api(`/catalog?q=${encodeURIComponent(code)}&limit=1`); const item = found.items.find((entry) => entry.stock_code === code); if (item) descriptions.set(code,item.description); }));
    renderRecommendations(result);
  } catch (error) { show($("#recommend-result"), `<strong>${t("recommendFailed")}</strong><br>${safe(error.message)}`,true); }
}
$("#assistant-form").addEventListener("submit",async (event) => { event.preventDefault(); try {
  const result = await api("/chat",{method:"POST",headers:$("#assistant-provider").value === "baseline" ? {} : {"X-Provider-Access":$("#provider-access").value},body:JSON.stringify({question:$("#question").value,intent_hint:$("#assistant-task").value,basket,provider:$("#assistant-provider").value,hosted_data_consent:$("#hosted-data-consent").checked})});
  if (result.intent === "recommendation") {
    result.tool_result.product_descriptions = {};
    await Promise.all((result.tool_result.recommendations || []).map(async (item) => { const found = await api(`/catalog?q=${encodeURIComponent(item.item)}&limit=1`); const product = found.items.find((row) => row.stock_code === item.item); if (product) result.tool_result.product_descriptions[item.item] = product.description; }));
  }
  lastAssistantResult = result; renderAssistant(result);
} catch(error) { show($("#assistant-result"), `<strong>${t("assistantFailed")}</strong><br>${safe(error.message)}`,true); } });
$("#staff-login-form").addEventListener("submit",async (event) => { event.preventDefault(); try {
  await api("/internal/staff/login",{method:"POST",body:JSON.stringify({username:$("#staff-username").value,password:$("#staff-password").value})});
  $("#staff-password").value = "";
  setStaffSignedIn(true);
} catch(error) { $("#staff-password").value = ""; show($("#staff-assistant-result"), `<strong>${t("staffSignInFailed")}</strong><br>${safe(error.message)}`,true); } });
$("#staff-logout").addEventListener("click",async () => { try { await api("/internal/staff/logout",{method:"POST"}); setStaffSignedIn(false); } catch(error) { show($("#staff-assistant-result"), `<strong>${t("assistantFailed")}</strong><br>${safe(error.message)}`,true); } });
$("#staff-assistant-form").addEventListener("submit",async (event) => { event.preventDefault(); try {
  const result = await api("/internal/staff/chat",{method:"POST",body:JSON.stringify({question:$("#staff-question").value})});
  lastStaffResult = result; renderAssistant(result,"#staff-assistant-result");
} catch(error) { if (error.message.includes("Staff sign-in required")) { setStaffSignedIn(false); show($("#staff-assistant-result"), safe(t("staffSessionExpired")),true); } else show($("#staff-assistant-result"), `<strong>${t("assistantFailed")}</strong><br>${safe(error.message)}`,true); } });
async function refreshMetrics() { try { const metrics = await api("/metrics"); $("#metric-requests").textContent = metrics.requests_total; $("#metric-errors").textContent = metrics.errors_total; $("#metric-error-rate").textContent = `${(metrics.error_rate*100).toFixed(1)}%`; $("#metric-latency").textContent = `${metrics.average_latency_ms.toFixed(1)} ms`; $("#alert-badge").textContent = metrics.alert_active?t("alert"):t("normal"); $("#alert-badge").className = `badge ${metrics.alert_active?"alert":"good"}`; } catch (_) { $("#alert-badge").textContent = t("unavailable"); } }
function driftLabel(name) { return name === "return_probability_90d" ? t("driftScore") : t(({recency_days:"recencyLabel",frequency_orders:"frequencyLabel",monetary_total:"spendLabel",unique_products:"productsLabel"})[name]); }
function driftStatusLabel(status) { return t(({stable:"driftStable",watch:"driftWatch",high:"driftHigh",insufficient:"driftInsufficient"})[status]); }
function renderDrift(result) {
  const rows = result.metrics.map((item) => `<tr><td>${safe(driftLabel(item.name))}</td><td>${safe(item.psi.toFixed(3))}</td><td>${safe((item.out_of_range_rate*100).toFixed(1))}%</td><td class="drift-${safe(item.status)}">${safe(driftStatusLabel(item.status))}</td></tr>`).join("");
  show($("#drift-result"), `<p><strong>${t("driftStatus")}: ${safe(driftStatusLabel(result.status))}</strong> · ${t("driftScoreStatus")}: ${safe(driftStatusLabel(result.score_status))} · ${t("driftSamples")}: ${result.sample_count} · ${safe(result.model_version)}</p><table><thead><tr><th>${t("driftMetric")}</th><th>${t("driftPsi")}</th><th>${t("driftRange")}</th><th>${t("driftIndicator")}</th></tr></thead><tbody>${rows}</tbody></table><p class="footnote">${t("driftCaution")}</p>`);
}
function sampleReference(name, index, offset) {
  const reference = driftReference.features[name];
  const target = ((index*37+offset)%100)/100;
  let cumulative = 0;
  for (let bin=0; bin<reference.reference_proportions.length; bin++) { cumulative += reference.reference_proportions[bin]; if (target < cumulative) return reference.sample_values[bin]; }
  return reference.sample_values.at(-1);
}
function driftProfiles(shifted) {
  return Array.from({length:100},(_,index) => {
    const values = shifted ? {recency_days:300+(index%20)*3,frequency_orders:1+(index%3===0?1:0),monetary_total:30+(index%20)*5,unique_products:2+(index%5)} : {
      recency_days:sampleReference("recency_days",index,0),frequency_orders:Math.max(1,Math.round(sampleReference("frequency_orders",index,17))),
      monetary_total:sampleReference("monetary_total",index,39),unique_products:Math.max(1,Math.round(sampleReference("unique_products",index,71)))
    };
    return {model_variant:"temporal",features:coherentRetentionProfile({...contract.synthetic_example,...values})};
  });
}
async function runDrift(shifted) {
  if (!contract || !driftReference) return;
  for (const id of ["#drift-reference-demo","#drift-shifted-demo"]) $(id).disabled = true;
  $("#drift-result").className = "result empty"; $("#drift-result").textContent = t("driftRunning");
  try { lastDriftResult = await api("/monitoring/drift/demo",{method:"POST",body:JSON.stringify({records:driftProfiles(shifted)})}); renderDrift(lastDriftResult); }
  catch (error) { show($("#drift-result"), `<strong>${t("driftFailed")}</strong><br>${safe(error.message)}`,true); }
  finally { for (const id of ["#drift-reference-demo","#drift-shifted-demo"]) $(id).disabled = false; }
}
$("#drift-reference-demo").addEventListener("click",()=>runDrift(false));
$("#drift-shifted-demo").addEventListener("click",()=>runDrift(true));
$("#normal-traffic").addEventListener("click",async () => { $("#traffic-status").textContent = t("normalStart"); await Promise.all(Array.from({length:8},()=>api("/health"))); $("#traffic-status").textContent = t("normalDone"); refreshMetrics(); });
$("#shifted-traffic").addEventListener("click",async () => { $("#traffic-status").textContent = t("shiftStart"); await Promise.allSettled(Array.from({length:8},()=>api("/predict",{method:"POST",body:JSON.stringify({features:{recency_days:-999}})}))); $("#traffic-status").textContent = t("shiftDone"); refreshMetrics(); });
async function initialize() {
  setLanguage(language);
  try { await api("/internal/staff/session"); setStaffSignedIn(true); } catch (_) { setStaffSignedIn(false); }
  try { const selection = await api("/assistant/providers"); for (const item of selection.providers) { const option = $("#assistant-provider").querySelector(`[value="${item.id}"]`); if (option) { option.disabled = !item.available; option.title = item.available ? (item.model || "") : t("providerUnavailable"); } } } catch (_) { for (const name of ["openai","huggingface","ollama"]) $("#assistant-provider").querySelector(`[value="${name}"]`).disabled = true; }
  try { const [ready,version,response] = await Promise.all([api("/ready"),api("/version"),api("/contract")]); contract = response; $("#retention-model").querySelector('[value="random_80_20"]').hidden = !response.model_variants.includes("random_80_20"); loadScenario(); readyState = ready.ready; $("#health-dot").classList.add("ready"); $("#health-label").textContent = ready.ready?t("ready"):t("degraded"); $("#version-label").textContent = `API ${version.service_version} · model ${version.model_version}`; await hydrateBasketDescriptions(); await searchCatalog(); getRecommendations(); }
  catch (error) { $("#health-label").textContent = t("unavailable"); $("#version-label").textContent = error.message; }
  try { const reference = await api("/monitoring/drift/reference"); if (reference.enabled && reference.model_version === contract?.model_version) { driftReference = reference; $("#drift-reference-status").textContent = t("driftReady"); $("#drift-reference-demo").disabled = false; $("#drift-shifted-demo").disabled = false; } else { $("#drift-reference-status").textContent = t("driftUnavailable"); } }
  catch (_) { $("#drift-reference-status").textContent = t("driftUnavailable"); }
  refreshMetrics();
}
initialize(); setInterval(refreshMetrics,5000);
