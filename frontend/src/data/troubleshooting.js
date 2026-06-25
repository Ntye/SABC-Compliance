// Troubleshooting knowledge base for the SABC compliance platform.
//
// Each entry documents a real problem encountered on the platform, its root
// cause, and the resolution. Content is bilingual (en/fr); the Help page picks
// the active language at render time. When you fix a new class of problem, add
// an entry here so the knowledge stays with the product.
//
// platform: 'sabc' | 'puppet' | 'wazuh' | 'general'
// severity: 'fixed'   → shipped fix, usually no user action needed
//           'action'  → requires an operator action (documented in steps)
//           'info'    → expected behaviour / good-to-know

export const PLATFORMS = [
  { key: 'sabc',    label: { en: 'SABC Compliance Platform', fr: 'Plateforme de conformité SABC' } },
  { key: 'puppet',  label: { en: 'Puppet Enterprise',        fr: 'Puppet Enterprise' } },
  { key: 'wazuh',   label: { en: 'Wazuh',                    fr: 'Wazuh' } },
  { key: 'general', label: { en: 'Cross-platform',           fr: 'Multi-plateforme' } },
]

export const TROUBLESHOOTING = [
  // ── SABC platform ──────────────────────────────────────────────────────────
  {
    id: 'sabc-500-node-groups',
    platform: 'sabc',
    severity: 'fixed',
    title: {
      en: 'HTTP 500 on the Node Groups page',
      fr: 'Erreur HTTP 500 sur la page Groupes de nœuds',
    },
    symptom: {
      en: 'Opening Node Groups returns "Internal Server Error" (500); the backend log shows "column ... does not exist".',
      fr: "L'ouverture des Groupes de nœuds renvoie « Internal Server Error » (500) ; le journal backend indique « column ... does not exist ».",
    },
    cause: {
      en: 'On PostgreSQL, the ORM only creates missing tables — it never adds new columns to tables that already exist. After a deploy that introduced columns like group_type and inspec_profile_id, queries failed because those columns were absent.',
      fr: "Sur PostgreSQL, l'ORM ne crée que les tables manquantes — il n'ajoute jamais de nouvelles colonnes aux tables existantes. Après un déploiement introduisant des colonnes comme group_type et inspec_profile_id, les requêtes échouaient car ces colonnes étaient absentes.",
    },
    steps: {
      en: [
        'Resolved in the platform: startup now runs idempotent "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" migrations for every new column, each in its own transaction.',
        'No action needed beyond redeploying the backend — the columns are added automatically on boot.',
      ],
      fr: [
        'Corrigé dans la plateforme : au démarrage, des migrations idempotentes « ALTER TABLE ... ADD COLUMN IF NOT EXISTS » sont exécutées pour chaque nouvelle colonne, chacune dans sa propre transaction.',
        "Aucune action requise au-delà du redéploiement du backend — les colonnes sont ajoutées automatiquement au démarrage.",
      ],
    },
  },
  {
    id: 'sabc-sync-no-puppet',
    platform: 'sabc',
    severity: 'action',
    title: {
      en: 'Sync reports success but nothing appears in the Puppet console',
      fr: 'La synchro réussit mais rien n’apparaît dans la console Puppet',
    },
    symptom: {
      en: 'The sync toast says e.g. "19/19 groups" yet the Puppet Enterprise console shows none of the SABC groups.',
      fr: 'La synchro affiche par ex. « 19/19 groupes » mais la console Puppet Enterprise n’affiche aucun groupe SABC.',
    },
    cause: {
      en: 'The classifier client had no Puppet master host, so every API call silently did nothing while the sync counted them as successful. The master host and PE console password live in the platform configuration (written when you install/connect the master), which the client was not reading.',
      fr: "Le client classifier n'avait pas d'hôte maître Puppet ; chaque appel API ne faisait donc rien en silence, tandis que la synchro les comptait comme réussis. L'hôte maître et le mot de passe console PE résident dans la configuration de la plateforme (écrits lors de l'installation/connexion du maître), que le client ne lisait pas.",
    },
    steps: {
      en: [
        'Resolved in the platform: the client now reads the master host + PE password from configuration on every call and reports honestly when no master is configured.',
        'Action: go to Infrastructure → Puppet master → "PE credentials" and save the correct console admin password.',
        'Confirm a master host is set (Infrastructure → Puppet master shows a host). Then re-run Sync on the Node Groups page.',
      ],
      fr: [
        'Corrigé dans la plateforme : le client lit désormais l’hôte maître + le mot de passe PE depuis la configuration à chaque appel et signale honnêtement l’absence de maître configuré.',
        'Action : allez dans Infrastructure → maître Puppet → « Identifiants PE » et enregistrez le bon mot de passe admin de la console.',
        'Vérifiez qu’un hôte maître est défini (Infrastructure → maître Puppet affiche un hôte). Puis relancez la synchro sur la page Groupes de nœuds.',
      ],
    },
  },
  {
    id: 'sabc-groups-not-created',
    platform: 'sabc',
    severity: 'info',
    title: {
      en: 'A node group is not created in Puppet until a matching node exists',
      fr: 'Un groupe de nœuds n’est créé dans Puppet qu’une fois un nœud correspondant présent',
    },
    symptom: {
      en: 'Empty OS-family groups (e.g. CentOS on an all-Ubuntu fleet) do not appear in the Puppet console.',
      fr: 'Les groupes de famille d’OS vides (ex. CentOS sur un parc 100 % Ubuntu) n’apparaissent pas dans la console Puppet.',
    },
    cause: {
      en: 'By design, a system group is materialised in Puppet only when it — or one of its descendants — actually matches a registered node. This keeps the console free of dozens of empty distro/version groups. Ancestors of a matched group are always created so the hierarchy is complete.',
      fr: "Par conception, un groupe système n'est créé dans Puppet que lorsqu'il — ou l'un de ses descendants — correspond réellement à un nœud enregistré. Cela évite des dizaines de groupes vides. Les ancêtres d'un groupe correspondant sont toujours créés pour que la hiérarchie soit complète.",
    },
    steps: {
      en: [
        'Register and enroll a node of that OS; on the next sync the matching branch (family → distro → version) appears automatically.',
        'All groups always remain visible in the SABC platform tree regardless of population — only the Puppet console is kept lean.',
      ],
      fr: [
        'Enregistrez et enrôlez un nœud de cet OS ; à la prochaine synchro, la branche correspondante (famille → distro → version) apparaît automatiquement.',
        'Tous les groupes restent toujours visibles dans l’arbre de la plateforme SABC quelle que soit leur population — seule la console Puppet est gardée allégée.',
      ],
    },
  },
  {
    id: 'sabc-nopasswd-ansible',
    platform: 'sabc',
    severity: 'info',
    title: {
      en: 'NOPASSWD:ALL for the automation user is not a compliance finding',
      fr: 'NOPASSWD:ALL pour le compte d’automatisation n’est pas une non-conformité',
    },
    symptom: {
      en: 'You expect the Ansible/automation account to keep NOPASSWD:ALL sudo without tripping the compliance scan.',
      fr: 'Vous souhaitez que le compte Ansible/automatisation conserve sudo NOPASSWD:ALL sans déclencher le scan de conformité.',
    },
    cause: {
      en: 'The automation user legitimately requires passwordless sudo to drive remediation. Flagging it would create permanent noise.',
      fr: "Le compte d'automatisation a légitimement besoin de sudo sans mot de passe pour piloter la remédiation. Le signaler créerait un bruit permanent.",
    },
    steps: {
      en: [
        'By design: the platform excludes the automation user from this control, so its NOPASSWD:ALL does not affect compliance.',
        'Any OTHER account holding NOPASSWD:ALL is still reported — that is a genuine privilege-escalation risk and should be removed.',
      ],
      fr: [
        "Par conception : la plateforme exclut le compte d'automatisation de ce contrôle, donc son NOPASSWD:ALL n'affecte pas la conformité.",
        'Tout AUTRE compte détenant NOPASSWD:ALL est toujours signalé — c’est un véritable risque d’élévation de privilèges et doit être supprimé.',
      ],
    },
  },

  // ── Puppet Enterprise ────────────────────────────────────────────────────
  {
    id: 'puppet-flat-hierarchy',
    platform: 'puppet',
    severity: 'fixed',
    title: {
      en: 'Node groups appear flat under "All Nodes" instead of nested',
      fr: 'Les groupes apparaissent à plat sous « All Nodes » au lieu d’être imbriqués',
    },
    symptom: {
      en: 'In the Puppet console, SABC groups (Ubuntu, Debian, RedHat Family…) all sit directly under All Nodes rather than nested SABC Managed Nodes → Family → Distro → Version.',
      fr: 'Dans la console Puppet, les groupes SABC (Ubuntu, Debian, RedHat Family…) sont directement sous All Nodes au lieu d’être imbriqués SABC Managed Nodes → Famille → Distro → Version.',
    },
    cause: {
      en: 'Groups created before their parent existed defaulted to the root, and subsequent updates only refreshed rules — never the parent — so the flat layout persisted.',
      fr: "Les groupes créés avant l'existence de leur parent étaient rattachés à la racine, et les mises à jour suivantes ne rafraîchissaient que les règles — jamais le parent — d'où la disposition à plat persistante.",
    },
    steps: {
      en: [
        'Resolved in the platform: the sync now processes groups parent-first (topological order) and re-parents existing groups to their correct place on every run.',
        'Action: redeploy the backend and click Sync once. The console hierarchy is corrected in place — no need to delete groups.',
      ],
      fr: [
        'Corrigé dans la plateforme : la synchro traite désormais les groupes parents d’abord (ordre topologique) et re-rattache les groupes existants à leur place correcte à chaque exécution.',
        'Action : redéployez le backend et cliquez une fois sur Synchro. La hiérarchie de la console est corrigée sur place — inutile de supprimer des groupes.',
      ],
    },
  },
  {
    id: 'puppet-rhel-missing',
    platform: 'puppet',
    severity: 'fixed',
    title: {
      en: 'No Red Hat Enterprise Linux (RHEL) group is created',
      fr: 'Aucun groupe Red Hat Enterprise Linux (RHEL) n’est créé',
    },
    symptom: {
      en: 'A RHEL host is registered and recognised, but no RHEL node group appears in either platform.',
      fr: 'Un hôte RHEL est enregistré et reconnu, mais aucun groupe de nœuds RHEL n’apparaît dans l’une ou l’autre plateforme.',
    },
    cause: {
      en: 'The seeded OS-family tree had Rocky, CentOS and AlmaLinux under the RedHat family but was missing a dedicated Red Hat Enterprise Linux branch.',
      fr: "L'arbre de familles d'OS pré-amorcé comportait Rocky, CentOS et AlmaLinux sous la famille RedHat mais il manquait une branche dédiée Red Hat Enterprise Linux.",
    },
    steps: {
      en: [
        'Resolved in the platform: a "Red Hat Enterprise Linux" distro group plus RHEL 7 / 8 / 9 version groups are now seeded under RedHat Family.',
        'Action: redeploy the backend (the tree is re-seeded idempotently on startup), then Sync. The RHEL branch appears once a RHEL host matches.',
      ],
      fr: [
        'Corrigé dans la plateforme : un groupe distro « Red Hat Enterprise Linux » et les groupes de version RHEL 7 / 8 / 9 sont désormais pré-amorcés sous RedHat Family.',
        'Action : redéployez le backend (l’arbre est ré-amorcé de façon idempotente au démarrage), puis Synchro. La branche RHEL apparaît dès qu’un hôte RHEL correspond.',
      ],
    },
  },
  {
    id: 'puppet-admin-lockout',
    platform: 'puppet',
    severity: 'action',
    title: {
      en: 'Locked out of the PE console (cannot log in as admin)',
      fr: 'Verrouillage de la console PE (connexion admin impossible)',
    },
    symptom: {
      en: 'The Puppet Enterprise console rejects the admin login even with the correct password.',
      fr: 'La console Puppet Enterprise rejette la connexion admin même avec le bon mot de passe.',
    },
    cause: {
      en: 'Repeated authentication attempts with a wrong stored password (e.g. an installer default that did not match the real one) trip PE’s failed-login lockout on the admin account.',
      fr: "Des tentatives d'authentification répétées avec un mauvais mot de passe stocké (ex. une valeur par défaut d'installateur différente de la vraie) déclenchent le verrouillage pour échecs de connexion sur le compte admin.",
    },
    steps: {
      en: [
        'On the Puppet master, clear the lockout in the RBAC database (column names verified for PE 2025.x):',
        'Restart the console services, then log in with the real password.',
        'Then store the correct password in SABC (Infrastructure → Puppet master → PE credentials) so the platform stops attempting the wrong one and never re-locks the account.',
      ],
      fr: [
        'Sur le maître Puppet, levez le verrouillage dans la base RBAC (noms de colonnes vérifiés pour PE 2025.x) :',
        'Redémarrez les services console, puis connectez-vous avec le vrai mot de passe.',
        'Ensuite, enregistrez le bon mot de passe dans SABC (Infrastructure → maître Puppet → Identifiants PE) pour que la plateforme cesse d’essayer le mauvais et ne reverrouille jamais le compte.',
      ],
    },
    code:
      "sudo su -s /bin/bash - pe-postgres -c \\\n" +
      "  \"/opt/puppetlabs/server/bin/psql -d pe-rbac -c \\\n" +
      "  \\\"UPDATE subjects SET failed_login_attempts = 0, is_revoked = false WHERE login = 'admin';\\\"\"\n\n" +
      "sudo puppet resource service pe-console-services ensure=stopped\n" +
      "sudo puppet resource service pe-console-services ensure=running",
  },
  {
    id: 'puppet-empty-members',
    platform: 'puppet',
    severity: 'info',
    title: {
      en: 'A group shows no members even though nodes match',
      fr: 'Un groupe n’affiche aucun membre alors que des nœuds correspondent',
    },
    symptom: {
      en: 'A freshly created group looks empty in the console right after sync.',
      fr: 'Un groupe fraîchement créé semble vide dans la console juste après la synchro.',
    },
    cause: {
      en: 'Puppet classifies a node by its reported facts, which only land after the agent next checks in. Until then, fact-based membership is not yet computed.',
      fr: "Puppet classe un nœud selon les faits qu'il rapporte, lesquels n'arrivent qu'au prochain rapport de l'agent. D'ici là, l'appartenance par faits n'est pas encore calculée.",
    },
    steps: {
      en: [
        'The platform mitigates this by pinning each matched node into the group rule by certname, so known members appear immediately.',
        'For newly enrolled agents, trigger a Puppet run (or wait for the next 30-minute check-in) to populate fact-based membership.',
      ],
      fr: [
        'La plateforme atténue cela en épinglant chaque nœud correspondant dans la règle du groupe par certname, afin que les membres connus apparaissent immédiatement.',
        'Pour les agents nouvellement enrôlés, déclenchez une exécution Puppet (ou attendez le prochain rapport de 30 min) pour peupler l’appartenance par faits.',
      ],
    },
  },

  // ── Wazuh ──────────────────────────────────────────────────────────────────
  {
    id: 'wazuh-agents-dark-after-move',
    platform: 'wazuh',
    severity: 'info',
    title: {
      en: 'Agents go dark after the Wazuh manager address changes',
      fr: 'Les agents disparaissent après un changement d’adresse du gestionnaire Wazuh',
    },
    symptom: {
      en: 'After repointing the Wazuh manager, previously-enrolled agents stop reporting.',
      fr: 'Après un changement de gestionnaire Wazuh, les agents déjà enrôlés cessent de rapporter.',
    },
    cause: {
      en: 'Agents keep contacting the old manager address until their configuration is updated.',
      fr: "Les agents continuent de contacter l'ancienne adresse du gestionnaire jusqu'à la mise à jour de leur configuration.",
    },
    steps: {
      en: [
        'The platform handles this: changing the manager host re-points every enrolled agent automatically to the new address.',
        'If an agent stays dark, check connectivity to the new manager on ports 1514/1515 and confirm DNS resolution.',
      ],
      fr: [
        'La plateforme gère cela : changer l’hôte du gestionnaire re-pointe automatiquement chaque agent enrôlé vers la nouvelle adresse.',
        'Si un agent reste muet, vérifiez la connectivité vers le nouveau gestionnaire sur les ports 1514/1515 et la résolution DNS.',
      ],
    },
  },
  {
    id: 'wazuh-enroll-dns',
    platform: 'wazuh',
    severity: 'action',
    title: {
      en: 'Agent fails to enroll (name resolution / connectivity)',
      fr: 'L’agent échoue à s’enrôler (résolution de nom / connectivité)',
    },
    symptom: {
      en: 'Agent installation completes but the node never registers with the manager.',
      fr: "L'installation de l'agent se termine mais le nœud ne s'enregistre jamais auprès du gestionnaire.",
    },
    cause: {
      en: 'The node cannot resolve the manager hostname, or registration/communication ports are blocked.',
      fr: "Le nœud ne peut pas résoudre le nom d'hôte du gestionnaire, ou les ports d'enregistrement/communication sont bloqués.",
    },
    steps: {
      en: [
        'Run the DNS check on the node (⚠ button in Node Registry) before enrolling — the platform auto-adds an /etc/hosts entry when a name does not resolve.',
        'Verify the manager is reachable on 1515 (registration) and 1514 (events) from the node.',
      ],
      fr: [
        'Lancez la vérification DNS sur le nœud (bouton ⚠ dans le Registre des nœuds) avant l’enrôlement — la plateforme ajoute automatiquement une entrée /etc/hosts quand un nom ne se résout pas.',
        'Vérifiez que le gestionnaire est joignable sur 1515 (enregistrement) et 1514 (événements) depuis le nœud.',
      ],
    },
  },

  // ── Cross-platform ───────────────────────────────────────────────────────
  {
    id: 'general-clock-skew',
    platform: 'general',
    severity: 'info',
    title: {
      en: 'Certificates rejected as "not yet valid" (clock skew)',
      fr: 'Certificats rejetés comme « pas encore valides » (décalage d’horloge)',
    },
    symptom: {
      en: 'Agent enrollment fails with certificate time-validity errors.',
      fr: 'L’enrôlement de l’agent échoue avec des erreurs de validité temporelle du certificat.',
    },
    cause: {
      en: 'The node clock is behind the signing authority, so a freshly issued certificate appears to be from the future.',
      fr: "L'horloge du nœud est en retard sur l'autorité de signature, donc un certificat fraîchement émis paraît venir du futur.",
    },
    steps: {
      en: [
        'The platform preflight installs and force-syncs NTP (chrony) before enrollment, so this is normally prevented.',
        'If it recurs, confirm the node can reach an NTP source and that chrony is running.',
      ],
      fr: [
        'Le préflight de la plateforme installe et force la synchro NTP (chrony) avant l’enrôlement, ce qui le prévient normalement.',
        'Si cela se reproduit, vérifiez que le nœud peut joindre une source NTP et que chrony est actif.',
      ],
    },
  },
]
