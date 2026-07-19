# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from app.web.manual_data import MANUAL_CHAPTERS

router = APIRouter()

# Detailed specific data for each of the 54 chapters (Bilingual)
SPECIFIC_CHAPTER_DATA = {
    '1-1': {
        'fr_title': '💡 Guide pas-à-pas : Démarrage rapide',
        'ar_title': '💡 خطوة بخطوة : البدء السريع',
        'fr_usage': ['Double-cliquez sur l\'icône du bureau.', 'Entrez votre code PIN par défaut.', 'Consultez les indicateurs clés.'],
        'ar_usage': ['انقر نقرًا مزدوجًا على أيقونة البرنامج.', 'أدخل رمز PIN الافتراضي.', 'راجع مؤشرات الأداء الحالية.'],
        'fr_example': 'Lancer l\'application et se connecter avec le compte administrateur en moins de 10 secondes.',
        'ar_example': 'تشغيل البرنامج والدخول باستخدام حساب المدير في أقل من 10 ثوانٍ.'
    },
    '1-2': {
        'fr_title': '🔒 Sécurisation de l\'accès',
        'ar_title': '🔒 تأمين الوصول للحساب',
        'fr_usage': ['Saisissez votre code PIN.', 'La session expire après 15 min d\'inactivité.', 'Bouton déconnexion en haut à droite.'],
        'ar_usage': ['أدخل رمز PIN الخاص بك.', 'تنتهي الجلسة تلقائيًا بعد 15 دقيقة من عدم الاستخدام.', 'زر تسجيل الخروج في أعلى اليمين.'],
        'fr_example': 'L\'opérateur se déconnecte avant de laisser son poste pour éviter les écritures non autorisées.',
        'ar_example': 'يقوم العامل بتسجيل الخروج قبل مغادرة مكتبه لتفادي أي عمليات غير مصرح بها.'
    },
    '1-3': {
        'fr_title': '📲 Couplage Mobile QR Link',
        'ar_title': '📲 ربط الهاتف برمز QR',
        'fr_usage': ['Allez dans Profil > Connexion Mobile.', 'Scannez le QR Code avec votre smartphone.', 'Validez l\'accès sur votre téléphone.'],
        'ar_usage': ['اذهب إلى الحساب > اتصال الهاتف.', 'امسح رمز QR باستخدام كاميرا الهاتف.', 'أكد الاتصال على شاشة الهاتف.'],
        'fr_example': 'Scanner le code dynamique pour suivre les ventes en direct depuis le dépôt avec votre smartphone.',
        'ar_example': 'مسح الرمز الديناميكي لمتابعة المبيعات مباشرة من المستودع بهاتفك المحمول.'
    },
    '1-4': {
        'fr_title': '🎨 Personnalisation thématique',
        'ar_title': '🎨 تخصيص المظهر والواجهة',
        'fr_usage': ['Cliquez sur l\'icône soleil/lune.', 'Sélectionnez la police préférée.', 'Activez la barre de navigation verticale.'],
        'ar_usage': ['انقر على رمز الشمس/الهلال.', 'اختر نوع الخط المفضل.', 'قم بتفعيل القائمة الجانبية العمودية.'],
        'fr_example': 'Choisir la police "Plus Jakarta" et le mode sombre pour un meilleur confort visuel nocturne.',
        'ar_example': 'اختيار خط "Plus Jakarta" والمظهر المظلم لراحة أفضل للعينين ليلاً.'
    },
    '1-5': {
        'fr_title': '🔑 Gestion de votre mot de passe',
        'ar_title': '🔑 إدارة وتغيير كلمة المرور',
        'fr_usage': ['Allez dans Profil > Sécurité.', 'Saisissez l\'ancien mot de passe.', 'Entrez et confirmez le nouveau code.'],
        'ar_usage': ['اذهب إلى الحساب > الأمان.', 'أدخل كلمة المرور القديمة.', 'أدخل الكود الجديد وأكده.'],
        'fr_example': 'Mettre à jour le code d\'accès chaque mois pour préserver l\'intégrité des comptes.',
        'ar_example': 'تحديث كود الدخول شهريًا لحماية سرية البيانات والحسابات.'
    },
    '1-6': {
        'fr_title': '🍪 Cookies de session & Sécurité web',
        'ar_title': '🍪 ملفات الارتباط وحماية الجلسة',
        'fr_usage': ['Le système utilise des cookies chiffrés.', 'Protection automatique contre les failles CSRF.', 'Ne pas partager sa session.'],
        'ar_usage': ['يستخدم النظام ملفات تعريف مشفرة.', 'حماية تلقائية ضد ثغرات الاختراق CSRF.', 'لا تشارك جلستك مع أجهزة أخرى.'],
        'fr_example': 'Les transferts de données sensibles vers le serveur local sont sécurisés et authentifiés.',
        'ar_example': 'تأمين نقل البيانات الحساسة إلى الخادم المحلي والتحقق من الهوية.'
    },
    '2-1': {
        'fr_title': '📊 Analyse des indicateurs financiers (KPIs)',
        'ar_title': '📊 تحليل مؤشرات الأداء المالي',
        'fr_usage': ['Consultez le bandeau supérieur du Dashboard.', 'Vérifiez le chiffre d\'affaires et les créances.', 'Les chiffres s\'actualisent en temps réel.'],
        'ar_usage': ['راجع الشريط العلوي في لوحة القيادة.', 'تحقق من حجم المبيعات والديون المستحقة.', 'تتحدث الأرقام تلقائيًا مع كل عملية بيع.'],
        'fr_example': 'Vérifier l\'encaisse physique du jour à la fermeture pour s\'assurer qu\'elle correspond au tiroir-caisse.',
        'ar_example': 'التحقق من المداخيل النقدية اليومية عند الإغلاق للتأكد من مطابقتها للصندوق.'
    },
    '2-2': {
        'fr_title': '📈 Visualisation graphique des performances',
        'ar_title': '📈 متابعة الرسوم البيانية للمبيعات',
        'fr_usage': ['Sélectionnez la période (Jour/Mois/Année).', 'Analysez les courbes d\'évolution.', 'Passez la souris sur les points pour les détails.'],
        'ar_usage': ['حدد الفترة الزمنية (يوم/شهر/سنة).', 'حلل منحنيات تطور الأرباح.', 'مرر الفأرة فوق النقاط لعرض التفاصيل.'],
        'fr_example': 'Comparer le volume des ventes du mois de Juin par rapport à celui de Mai pour ajuster les stocks.',
        'ar_example': 'مقارنة حجم مبيعات شهر جوان بشهر ماي لتعديل كميات الشراء.'
    },
    '2-3': {
        'fr_title': '💬 Sabrina (IA) et validation d\'opérations',
        'ar_title': '💬 سابرينا المساعد الذكي وتأكيد العمليات',
        'fr_usage': ['Posez une question à Sabrina par écrit.', 'L\'IA analyse et prépare l\'action.', 'Cliquez sur "Confirmer" pour enregistrer.'],
        'ar_usage': ['اكتب سؤالك أو طلبك لسابرينا.', 'يقوم الذكاء الاصطnaعي بتحليل الطلب وتحضيره.', 'اضغط على زر "تأكيد" لحفظ العملية.'],
        'fr_example': 'Dire "Enregistre un paiement de 10000 DA de Amar" et valider le widget généré par l\'IA.',
        'ar_example': 'كتابة "سجل دفعة بقيمة 10000 دج لعمار" ثم الضغط على تأكيد وحفظ.'
    },
    '2-4': {
        'fr_title': '📜 Suivi de l\'historique des conversations',
        'ar_title': '📜 متابعة وتعديل سجل المحادثات',
        'fr_usage': ['Ouvrez l\'historique du chat.', 'Renommez un fil de discussion pour le retrouver.', 'Supprimez les anciennes conversations inutiles.'],
        'ar_usage': ['افتح سجل المحادثات السابقة.', 'أعد تسمية المحادثة لتسهيل العثور عليها.', 'احذف المحادثات القديمة وغير الضرورية.'],
        'fr_example': 'Renommer une conversation "Analyse Dette Karim Juillet" pour s\'y référer plus tard.',
        'ar_example': 'إعادة تسمية محادثة إلى "تحليل ديون كريم جويلية" للرجوع إليها لاحقًا.'
    },
    '2-5': {
        'fr_title': '📉 Évaluation et rapports de tendances',
        'ar_title': '📉 تحليل ومقارنة اتجاهات السوق',
        'fr_usage': ['Consultez le comparatif J-7.', 'Identifiez les produits les plus vendus.', 'Adaptez vos tarifs selon l\'évolution du marché.'],
        'ar_usage': ['راجع مقارنة المبيعات مع الأسبوع الماضي.', 'حدد السلع الأكثر طلبًا في السوق.', 'عدل أسعار البيع بناءً على التغيرات.'],
        'fr_example': 'Constater une hausse de 15% sur l\'aliment bovin et commander plus de matières premières.',
        'ar_example': 'ملاحظة زيادة بـ 15% في طلب علف التسمين وزيادة كمية المواد الأولية.'
    },
    '2-6': {
        'fr_title': '🔔 Notifications instantanées WebSocket',
        'ar_title': '🔔 التنبيهات الفورية والمزامنة',
        'fr_usage': ['Les alertes apparaissent en haut de l\'écran.', 'S\'affiche lors d\'un stock bas ou d\'un backup.', 'Cliquez sur le badge pour lire.'],
        'ar_usage': ['تظهر التنبيهات فورًا في أعلى الشاشة.', 'تنبيه عند انخفاض المخزون أو إتمام النسخ.', 'انقر على أيقونة الجرس للتفاصيل.'],
        'fr_example': 'Recevoir une alerte sonore et visuelle immédiate quand le stock de Son de Blé atteint 0 sac.',
        'ar_example': 'تلقي تنبيه فوري بالصوت والصورة عند نفاد مادة النخالة من المستودع.'
    },
    '3-1': {
        'fr_title': '👥 Création et modification des clients',
        'ar_title': '👥 إضافة وتعديل بطاقات العملاء',
        'fr_usage': ['Allez dans Contacts > Clients.', 'Remplissez le nom, téléphone et solde de départ.', 'La suppression est bloquée si le client a des bons.'],
        'ar_usage': ['اذهب إلى جهات الاتصال > العملاء.', 'أدخل الاسم، الهاتف، والرصيد الافتتاحي.', 'يُحظر حذف الزبون إذا كانت له فواتير.'],
        'fr_example': 'Créer la fiche de "Aanouche Amar" avec une dette initiale de 68 850 DA.',
        'ar_example': 'إنشاء بطاقة زبون باسم "عنوش عمار" مع دين أولي بقيمة 68,850 دج.'
    },
    '3-2': {
        'fr_title': '📥 Importation Excel pas-à-pas',
        'ar_title': '📥 دليل استيراد البيانات من إكسل',
        'fr_usage': ['Utilisez un fichier Excel par client.', 'Le système lit la dernière ligne comme dette finale.', 'Vérifiez la prévisualisation avant validation.'],
        'ar_usage': ['استخدم ملف إكسل مستقل لكل زبون.', 'يعتمد البرنامج السطر الأخير كدين نهائي.', 'راجع جدول البيانات جيدًا قبل التأكيد.'],
        'fr_example': 'Importer Aanouche_Amar.xlsx contenant 25 lignes. Le solde final de 318 150 DA devient sa dette actuelle.',
        'ar_example': 'استيراد ملف Aanouche_Amar.xlsx يحتوي على 25 حركة، ليعتمد رصيد 318,150 دج كدين للزبون.'
    },
    '3-3': {
        'fr_title': '⏸️ Contrôle de la barre de progrès d\'import',
        'ar_title': '⏸️ شريط التقدم واستيراد الملفات الكبيرة',
        'fr_usage': ['Suivez la progression de l\'import en temps réel.', 'Bouton Pause pour suspendre le traitement.', 'Reprenez ou annulez à tout moment.'],
        'ar_usage': ['تابع تقدم عملية الاستيراد في الوقت الفعلي.', 'اضغط على زر إيقاف مؤقت لتعليق العملية.', 'استأنف الاستيراد أو ألغه في أي وقت.'],
        'fr_example': 'Mettre en pause l\'import d\'un lot de 100 fichiers clients pour vérifier une information, puis reprendre.',
        'ar_example': 'إيقاف استيراد 100 ملف عميل مؤقتًا للتحقق من معلومة، ثم الاستئناف.'
    },
    '3-4': {
        'fr_title': '🏢 Gestion des fournisseurs et de leurs soldes',
        'ar_title': '🏢 إدارة الموردين وحسابات الشراء',
        'fr_usage': ['Allez dans Contacts > Fournisseurs.', 'Suivez vos dettes d\'achats de matières premières.', 'Réglez les factures pour mettre à jour le solde.'],
        'ar_usage': ['اذهب إلى جهات الاتصال > الموردون.', 'تابع ديون شراء المواد الأولية للمطحنة.', 'سجل المدفوعات لتحديث رصيد المورد.'],
        'fr_example': 'Enregistrer une dette de 150 000 DA auprès du fournisseur "Moulins d\'Alger".',
        'ar_example': 'تسجيل دين شراء بقيمة 150,000 دج لمورد المواد الأولية "مطاحن الجزائر".'
    },
    '3-5': {
        'fr_title': '🧹 Fusion des fiches clients dupliquées',
        'ar_title': '🧹 دمج حسابات العملاء المتكررة',
        'fr_usage': ['Sélectionnez l\'outil de fusion.', 'Choisissez la fiche principale à conserver.', 'Fusionnez pour regrouper tous les historiques financiers.'],
        'ar_usage': ['اختر أداة دمج الحسابات المتكررة.', 'حدد الحساب الرئيسي الذي تريد الاحتفاظ به.', 'اضغط دمج لتوحيد الحركات المالية والحسابات.'],
        'fr_example': 'Fusionner "Aanouche A." avec "Aanouche Amar" pour regrouper leurs transactions sous une seule fiche.',
        'ar_example': 'دمج حساب "عنوش ع." مع حساب "عنوش عمار" لتوحيد كشف الحساب والرصيد.'
    },
    '3-6': {
        'fr_title': '📤 Exportation des contacts vers Excel',
        'ar_title': '📤 تصدير جهات الاتصال إلى ملف إكسل',
        'fr_usage': ['Allez dans la liste des contacts.', 'Cliquez sur le bouton "Exporter".', 'Le fichier se télécharge dans votre dossier de téléchargements.'],
        'ar_usage': ['اذهب إلى قائمة جهات الاتصال.', 'اضغط على زر "تصدير القائمة".', 'يتم تحميل ملف Excel مباشرة في جهازك.'],
        'fr_example': 'Exporter la liste complète des clients débiteurs pour faire un point de recouvrement hors ligne.',
        'ar_example': 'تصدير قائمة الزبائن الذين لديهم ديون لمراجعتها ومتابعة التحصيل.'
    },
    '4-1': {
        'fr_title': '🛒 Saisie d\'une vente à crédit ou versement',
        'ar_title': '🛒 تسجيل عملية بيع أو تحصيل نقد',
        'fr_usage': ['Ouvrez Opérations > Nouvelle Vente.', 'Sélectionnez l\'article, saisissez la quantité.', 'Le solde restant se met à jour instantanément.'],
        'ar_usage': ['افتح العمليات > بيع جديد.', 'اختر المادة وأدخل الكمية المباعة.', 'يتم حساب وتحديث الدين المتبقي في نفس اللحظة.'],
        'fr_example': 'Vente de 20 sacs d\'orge à crédit pour 92 000 DA, le solde du client augmente automatiquement.',
        'ar_example': 'بيع 20 كيس شعير بقيمة 92,000 دج بالدين، يرتفع رصيد دين الزبون تلقائيًا.'
    },
    '4-2': {
        'fr_title': '📦 Approvisionnement & Prix d\'achat moyen pondéré (PAMP)',
        'ar_title': '📦 تسجيل المشتريات وحساب متوسط التكلفة',
        'fr_usage': ['Enregistrez vos achats de matières premières.', 'Renseignez le prix d\'achat unitaire.', 'Le PAMP est recalculé pour évaluer le coût de revient.'],
        'ar_usage': ['سجل فواتير شراء المواد الأولية.', 'أدخل سعر شراء الوحدة للمادة.', 'يُعيد النظام حساب متوسط السعر لتحديد تكلفة الإنتاج.'],
        'fr_example': 'Achat de 100 quintaux de maïs. Le PAMP s\'ajuste pour refléter le coût moyen réel en stock.',
        'ar_example': 'شراء 100 قنطار مايس. يتعدل متوسط التكلفة تلقائيًا حسب السعر الجديد.'
    },
    '4-3': {
        'fr_title': '🗑️ Annulation et édition de bons (recalcul en cascade)',
        'ar_title': '🗑️ تعديل أو حذف الفواتير (تعديل الأرصدة التسلسلي)',
        'fr_usage': ['Ouvrez la liste des bons.', 'Cliquez sur Modifier ou Annuler.', 'Les soldes de toutes les opérations suivantes sont recalculés.'],
        'ar_usage': ['افتح قائمة الفواتير والوصولات.', 'اضغط على تعديل أو حذف العملية.', 'يقوم النظام تلقائيًا بإعادة حساب الأرصدة المتعاقبة.'],
        'fr_example': 'Supprimer une vente d\'il y a 3 mois recalcule automatiquement le solde de toutes les transactions qui ont suivi.',
        'ar_example': 'حذف وصل بيع منذ 3 أشهر يعيد حساب رصيد الزبون لجميع العمليات التي تلت ذلك التاريخ.'
    },
    '4-4': {
        'fr_title': '📄 Édition de l\'extrait de compte client',
        'ar_title': '📄 استخراج كشوف حسابات الزبائن',
        'fr_usage': ['Allez sur la fiche du client.', 'Consultez l\'extrait chronologique.', 'Imprimez en PDF pour le remettre au client.'],
        'ar_usage': ['افتح بطاقة الزبون الخاصة.', 'راجع كشف الحركة التفصيلي.', 'اطبع المستند بصيغة PDF لتسليمه للزبون.'],
        'fr_example': 'Imprimer l\'extrait de compte d\'Aanouche Amar montrant le détail de ses 25 opérations pour valider sa dette de 318 150 DA.',
        'ar_example': 'طباعة كشف حساب مفصل لعنوش عمار يوضح حركاته الـ 25 لتأكيد دينه البالغ 318,150 دج.'
    },
    '4-5': {
        'fr_title': '💵 Enregistrement d\'avances et acomptes',
        'ar_title': '💵 تسجيل العربون والتسبيقات المالية',
        'fr_usage': ['Lors du paiement, sélectionnez le type "Acompte".', 'Ce montant est déduit de la future facture.', 'Suivez les acomptes en attente.'],
        'ar_usage': ['عند تسجيل الدفعة، حدد خيار "عربون".', 'يتم خصم هذا المبلغ تلقائيًا من الفاتورة القادمة.', 'تابع مبالغ العربون المعلقة للزبائن.'],
        'fr_example': 'Recevoir un acompte de 20 000 DA pour réserver un lot d\'aliment de bétail à fabriquer.',
        'ar_example': 'قبض عربون بقيمة 20,000 دج لحجز كمية من الأعلاف قبل تصنيعها.'
    },
    '4-6': {
        'fr_title': '📜 Consultation du journal global des transactions',
        'ar_title': '📜 تصفح السجل العام للمبيعات والتحصيلات',
        'fr_usage': ['Allez dans Opérations > Historique.', 'Filtrez par type d\'opération ou par date.', 'Utilisez la recherche pour retrouver un numéro de bon.'],
        'ar_usage': ['اذهب إلى العمليات > السجل العام.', 'قم بالتصفية حسب نوع العملية أو التاريخ.', 'استخدم شريط البحث للبحث عن رقم فاتورة معين.'],
        'fr_example': 'Filtrer l\'historique pour afficher uniquement les versements du mois en cours afin de faire le point de caisse.',
        'ar_example': 'تصفية السجل لعرض المدفوعات النقدية المقبوضة هذا الشهر فقط لمراجعة حركة الصندوق.'
    },
    '5-1': {
        'fr_title': '📋 Définition des formules de recettes',
        'ar_title': '📋 إعداد وتعديل بطاقات وصفات الأعلاف',
        'fr_usage': ['Allez dans Production > Recettes.', 'Saisissez le nom du produit fini.', 'Définissez le pourcentage de chaque matière première.'],
        'ar_usage': ['اذهب إلى الإنتاج > الوصفات.', 'أدخل اسم المنتج النهائي.', 'حدد نسب المكونات والمواد الأولية بدقة.'],
        'fr_example': 'Créer la recette "Aliment Mouton standard" composée de 60% d\'orge et 40% de son de blé.',
        'ar_example': 'إنشاء وصفة "علف أغنام عادي" تتكون من 60% شعير و 40% نخالة.'
    },
    '5-2': {
        'fr_title': '🏭 Lancement d\'un ordre de fabrication',
        'ar_title': '🏭 إطلاق وتأكيد عمليات الإنتاج والتصنيع',
        'fr_usage': ['Allez dans Production > Lancer.', 'Sélectionnez la recette et la quantité.', 'Le stock d\'ingrédients est déduit automatiquement.'],
        'ar_usage': ['اذهب إلى الإنتاج > إطلاق إنتاج.', 'حدد الوصفة والكمية المراد إنتاجها.', 'يتم خصم مكونات الخلطة من مخزن المواد الأولية تلقائيًا.'],
        'fr_example': 'Produire 50 sacs d\'aliment consomme immédiatement les matières premières correspondantes en stock.',
        'ar_example': 'إنتاج 50 كيس علف يخصم كميات الشعير والنخالة المطلوبة من المخزون فورًا.'
    },
    '5-3': {
        'fr_title': '📦 Alertes de niveau de stock minimum',
        'ar_title': '📦 مراقبة المخازن وتنبيهات المستوى الأدنى',
        'fr_usage': ['Configurez le seuil d\'alerte pour chaque article.', 'Le système clignote en rouge en cas de stock bas.', 'Réapprovisionnez pour lever l\'alerte.'],
        'ar_usage': ['حدد حد التنبيه الأدنى لكل مادة.', 'يتحول لون المادة للأحمر عند انخفاض الكمية.', 'قم بالشراء وتعبئة المخزن لإلغاء التنبيه.'],
        'fr_example': 'Le maïs passe sous la barre des 10 quintaux, déclenchant une alerte de réapprovisionnement.',
        'ar_example': 'انخفاض مخزون المايس إلى أقل من 10 قناطير يطلق تنبيهًا لشراء السلعة وتفادي التوقف.'
    },
    '5-4': {
        'fr_title': '📜 Suivi de l\'historique des productions',
        'ar_title': '📜 مراجعة وتتبع سجل عمليات التصنيع',
        'fr_usage': ['Allez dans Production > Historique.', 'Consultez les dates et quantités produites.', 'Suivez le rendement de l\'usine par période.'],
        'ar_usage': ['اذهب إلى الإنتاج > سجل التصنيع.', 'راجع تواريخ وكميات الأعلاف المنتجة.', 'تابع إنتاجية المطحنة اليومية والأسبوعية.'],
        'fr_example': 'Consulter l\'historique pour vérifier le nombre de sacs produits la semaine dernière.',
        'ar_example': 'مراجعة السجل للتأكد من كمية أكياس الأعلاف المنتجة الأسبوع الماضي.'
    },
    '5-5': {
        'fr_title': '🍂 Déclaration de pertes ou déchets de matières',
        'ar_title': '🍂 تسجيل كميات الضياع والتلف للمواد الأولية',
        'fr_usage': ['Sélectionnez l\'ingrédient concerné.', 'Saisissez la quantité perdue.', 'Sélectionnez le motif (humidité, poussière).'],
        'ar_usage': ['حدد المادة الأولية المتضررة.', 'أدخل الكمية التالفة أو المفقودة.', 'اختر سبب التلف (رطوبة، غبار، أكياس ممزقة).'],
        'fr_example': 'Enregistrer une perte de 15 kg d\'orge suite à des dommages causés par l\'humidité.',
        'ar_example': 'تسجيل تلف 15 كغ من الشعير بسبب تعرضها للرطوبة في المستودع.'
    },
    '5-6': {
        'fr_title': '🧮 Évaluation du coût de revient industriel',
        'ar_title': '🧮 حساب تكلفة الإنتاج والربح المتوقع',
        'fr_usage': ['Allez sur la fiche recette.', 'Consultez le coût de revient calculé.', 'Le système base le calcul sur le prix d\'achat moyen.'],
        'ar_usage': ['افتح بطاقة الوصفة المطلوبة.', 'راجع تكلفة الإنتاج التقديرية للكيس.', 'يعتمد البرنامج على متوسط سعر شراء المواد لحساب التكلفة.'],
        'fr_example': 'Vérifier que le coût de revient d\'un sac d\'aliment est de 1 200 DA pour fixer un prix de vente rentable.',
        'ar_example': 'التأكد من أن تكلفة إنتاج الكيس هي 1200 دج لتحديد سعر بيع يضمن هامش ربح مناسب.'
    },
    '6-1': {
        'fr_title': '💸 Enregistrement des charges et dépenses annexes',
        'ar_title': '💸 تسجيل المصاريف والتكاليف العامة',
        'fr_usage': ['Allez dans Outils > Dépenses.', 'Saisissez le montant et la catégorie.', 'Ces charges diminuent automatiquement le bénéfice net.'],
        'ar_usage': ['اذهب إلى الأدوات > المصاريف.', 'أدخل قيمة المصاريف وفئتها.', 'تخصم هذه التكاليف مباشرة من صافي الأرباح اليومية.'],
        'fr_example': 'Enregistrer une facture d\'électricité Sonelgaz de 8 500 DA.',
        'ar_example': 'تسجيل فاتورة الكهرباء والغاز بقيمة 8,500 دج كدورة مصاريف.'
    },
    '6-2': {
        'fr_title': '📝 Utilisation du bloc-notes intégré',
        'ar_title': '📝 تدوين المهام في دفتر الملاحظات المدمج',
        'fr_usage': ['Ouvrez le bloc-notes depuis les outils.', 'Saisissez vos rappels ou tâches.', 'Les notes restent sauvegardées pour votre compte.'],
        'ar_usage': ['افتح دفتر الملاحظات من قائمة الأدوات.', 'أدخل تذكيراتك اليومية أو مهامك.', 'تظل الملاحظات محفوظة ومقترنة بحسابك الشخصي.'],
        'fr_example': 'Noter "Rappeler le client Lotfi pour son chèque lundi prochain".',
        'ar_example': 'تدوين ملاحظة "الاتصال بالزبون لطفي بخصوص الصك يوم الإثنين المقبل".'
    },
    '6-3': {
        'fr_title': '🗃️ Consultation du catalogue des produits',
        'ar_title': '🗃️ تصفح دليل المواد والسلع المتوفرة',
        'fr_usage': ['Allez dans Produits > Catalogue.', 'Consultez les prix et stocks disponibles.', 'Ajoutez ou modifiez les fiches articles.'],
        'ar_usage': ['اذهب إلى المنتجات > دليل السلع.', 'راجع الأسعار والكميات المتوفرة في المخزن.', 'أضف سلعًا جديدة أو عدل بيانات الحالية.'],
        'fr_example': 'Consulter le catalogue pour vérifier s\'il reste assez d\'Aliment Mouton avant de valider une grosse commande.',
        'ar_example': 'مراجعة دليل السلع للتأكد من توفر علف الأغنام قبل قبول طلبية كبيرة.'
    },
    '6-4': {
        'fr_title': '💰 Ajustement dynamique des tarifs de vente',
        'ar_title': '💰 تعديل أسعار البيع وتحديث القوائم',
        'fr_usage': ['Ouvrez la fiche du produit.', 'Modifiez le prix de vente.', 'Le nouveau tarif est appliqué pour toutes les prochaines ventes.'],
        'ar_usage': ['افتح بطاقة السلعة المراد تعديل سعرها.', 'أدخل سعر البيع الجديد.', 'يطبق السعر الجديد تلقائيًا في جميع فواتير البيع القادمة.'],
        'fr_example': 'Augmenter le prix du sac d\'aliment de 50 DA suite à la hausse du cours mondial de l\'orge.',
        'ar_example': 'زيادة سعر كيس العلف بـ 50 دج نظير ارتفاع أسعار الشعير في السوق.'
    },
    '6-5': {
        'fr_title': '🔍 Recherche multicritères intelligente',
        'ar_title': '🔍 استخدام البحث السريع والمتقدم',
        'fr_usage': ['Cliquez sur la barre de recherche en haut.', 'Saisissez un nom, un numéro de bon.', 'Le système affiche les résultats instantanément.'],
        'ar_usage': ['انقر على شريط البحث العلوي الموحد.', 'أدخل اسم زبون، رقم وصل، أو سلعة.', 'يعرض النظام النتائج المتطابقة مباشرة أثناء الكتابة.'],
        'fr_example': 'Saisir "318150" pour retrouver instantanément la fiche de compte d\'Aanouche Amar.',
        'ar_example': 'كتابة "318150" للوصول فورًا لبطاقة حساب الزبون عنوش عمار.'
    },
    '6-6': {
        'fr_title': '🧮 Utilisation de la calculatrice intégrée',
        'ar_title': '🧮 الآلة الحاسبة المدمجة لحساب المبيعات',
        'fr_usage': ['Cliquez sur l\'icône de calculatrice.', 'Effectuez vos calculs sans quitter la page.', 'Fermez-la en recliquant sur l\'icône.'],
        'ar_usage': ['انقر على رمز الآلة الحاسبة في الشريط العلوي.', 'قم بالعمليات الحسابية دون الحاجة للخروج من الصفحة.', 'اغلقها بالنقر على نفس الرمز.'],
        'fr_example': 'Calculer rapidement la remise à accorder sur un lot de 50 sacs d\'aliment.',
        'ar_example': 'حساب قيمة الخصم الممنوح لزبون عند شراء 50 كيسًا علفيًا.'
    },
    '7-1': {
        'fr_title': '📂 Explorateur et suivi des bons de livraison',
        'ar_title': '📂 مستعرض ومتابع وصولات التسليم',
        'fr_usage': ['Allez dans l\'Espace Bons.', 'Consultez la liste chronologique des bons générés.', 'Filtrez par client pour retrouver un historique.'],
        'ar_usage': ['افتح مساحة الوصولات والفواتير.', 'تصفح قائمة وصولات التسليم الصادرة مرتبة زمنيًا.', 'صفِ القائمة حسب الزبون للعثور على فواتيره.'],
        'fr_example': 'Retrouver le bon de livraison n°45 émis le mois dernier pour vérifier la quantité livrée.',
        'ar_example': 'البحث عن وصل التسليم رقم 45 الصادر الشهر الماضي للتحقق من الكميات المستلمة.'
    },
    '7-2': {
        'fr_title': '🖨️ Choix des formats d\'impression PDF (A4/A5)',
        'ar_title': '🖨️ طباعة الفواتير بقياس A4 أو A5 PDF',
        'fr_usage': ['Sélectionnez le document à imprimer.', 'Choisissez le format A4 pour dossier ou A5 pour le client.', 'Cliquez sur Imprimer.'],
        'ar_usage': ['حدد المستند أو الفاتورة المراد طباعتها.', 'اختر قياس A4 للأرشفة أو A5 الاقتصادي للتسليم.', 'اضغط على زر طباعة المستند.'],
        'fr_example': 'Générer un relevé de compte au format A5 compact pour le remettre en main propre au client.',
        'ar_example': 'استخراج كشف حساب بقياس A5 الاقتصادي لتسليمه للزبون يدًا بيد.'
    },
    '7-3': {
        'fr_title': '📥 Exportation des rapports au format Excel / CSV',
        'ar_title': '📥 تصدير البيانات إلى جداول Excel أو CSV',
        'fr_usage': ['Ouvrez le rapport ou la liste à exporter.', 'Cliquez sur le bouton "Exporter".', 'Sélectionnez le format Excel (.xlsx).'],
        'ar_usage': ['افتح التقرير أو القائمة التي تريد تصديرها.', 'اضغط على زر "تصدير البيانات".', 'اختر صيغة Excel (.xlsx) لتحميل الملف.'],
        'fr_example': 'Exporter le bilan des ventes mensuelles pour le transmettre à votre comptable.',
        'ar_example': 'تصدير جدول المبيعات الشهرية لتسليمه للمحاسب القانوني للمؤسسة.'
    },
    '7-4': {
        'fr_title': '🧾 Impression de tickets de caisse thermiques',
        'ar_title': '🧾 طباعة الفواتير على الورق الحراري 80 مم',
        'fr_usage': ['Sélectionnez le bon de vente.', 'Cliquez sur "Imprimer Ticket".', 'Le ticket est formaté pour imprimante 80mm.'],
        'ar_usage': ['حدد وصل البيع أو الدفع.', 'اضغط على زر "طباعة تذكرة".', 'يتم تنسيق الوصل تلقائيًا ليناسب طابعات الورق 80 مم.'],
        'fr_example': 'Imprimer un ticket thermique rapide pour un client qui emporte ses sacs immédiatement.',
        'ar_example': 'طباعة وصل حراري سريع لزبون يستلم بضاعته مباشرة من المخزن.'
    },
    '7-5': {
        'fr_title': '✒️ Personnalisation des entêtes et logos de l\'entreprise',
        'ar_title': '✒️ ضبط وإعداد ترويسة وشعار المؤسسة',
        'fr_usage': ['Allez dans Paramètres > Entête.', 'Saisissez le nom de l\'entreprise et l\'adresse.', 'Importez le fichier logo (JPG/PNG).'],
        'ar_usage': ['اذهب إلى الإعدادات > ترويسة الفاتورة.', 'أدخل اسم المؤسسة، العنوان، ورقم الهاتف.', 'ارفع شعار المؤسسة بصيغة JPG أو PNG.'],
        'fr_example': 'Ajouter votre numéro de téléphone et le logo du dépôt sur tous les bons imprimés.',
        'ar_example': 'إدراج شعار المستودع ورقم الهاتف في ترويسة جميع الوصولات المطبوعة.'
    },
    '7-6': {
        'fr_title': '✍️ Configuration de la signature et du cachet',
        'ar_title': '✍️ إعداد التوقيع والختم التلقائي للفواتير',
        'fr_usage': ['Importez l\'image de votre signature ou cachet.', 'Activez l\'affichage sur les documents PDF.', 'Configurez la position sur le bon.'],
        'ar_usage': ['ارفع صورة الختم والتوقيع الرقمي الخاص بك.', 'قم بتفعيل ميزة إدراج الختم تلقائيًا في مستندات PDF.', 'اضبط موضع الختم أسفل الوصل.'],
        'fr_example': 'Afficher automatiquement le cachet humide de l\'entreprise sur les factures envoyées par e-mail.',
        'ar_example': 'إدراج الختم والتوقيع تلقائيًا أسفل فواتير البيع المصدرة كـ PDF.'
    },
    '8-1': {
        'fr_title': '⚙️ Configuration de la clé d\'API Gemini (Sabrina)',
        'ar_title': '⚙️ ضبط إعدادات مفتاح الذكاء الاصطناعي',
        'fr_usage': ['Allez dans Admin > IA.', 'Saisissez votre clé d\'API Gemini.', 'Sélectionnez le modèle d\'IA (Flash/Pro).'],
        'ar_usage': ['اذهب إلى الإدارة > إعدادات الذكاء الاصطناعي.', 'أدخل مفتاح API الخاص بجوجل جيميناي.', 'اختر نموذج الذكاء الاصطناعي المناسب.'],
        'fr_example': 'Enregistrer la clé API générée gratuitement sur Google AI Studio pour activer Sabrina.',
        'ar_example': 'حفظ مفتاح الـ API المجاني من موقع Google AI Studio لتفعيل المساعدة سابرينا.'
    },
    '8-2': {
        'fr_title': '💾 Sauvegardes automatiques et restauration de base',
        'ar_title': '💾 النسخ الاحتياطي التلقائي واسترجاع البيانات',
        'fr_usage': ['Activez la sauvegarde automatique.', 'Configurez le dossier local de destination.', 'Utilisez la restauration en cas de problème.'],
        'ar_usage': ['فعل خيار النسخ الاحتياطي التلقائي.', 'حدد مسار الحفظ الاحتياطي على القرص الصلب.', 'استخدم ميزة استرجاع البيانات عند الحاجة.'],
        'fr_example': 'Restaurer la base de données à partir de la sauvegarde automatique de la veille suite à une fausse manipulation.',
        'ar_example': 'استرجاع قاعدة البيانات من نسخة الأمس الاحتياطية لتفادي خطأ في تسجيل العمليات.'
    },
    '8-3': {
        'fr_title': '🔑 Gestion des comptes utilisateurs et rôles',
        'ar_title': '🔑 إدارة حسابات المستخدمين وصلاحياتهم',
        'fr_usage': ['Allez dans Admin > Utilisateurs.', 'Créez un nouveau compte.', 'Définissez le rôle (Admin, Manager, Opérateur).'],
        'ar_usage': ['اذهب إلى الإدارة > حسابات المستخدمين.', 'أنشئ حسابًا جديدًا للعاملين.', 'حدد صلاحيات الحساب (مدير، مسير، عامل).'],
        'fr_example': 'Créer un compte de rôle "Operator" pour le nouveau vendeur du dépôt avec son propre PIN.',
        'ar_example': 'إنشاء حساب بصلاحية "عامل" للبائع الجديد في المستودع برقم PIN مستقل.'
    },
    '8-4': {
        'fr_title': '🕵️ Consultation du journal d\'audit de sécurité',
        'ar_title': '🕵️ مراجعة سجل الرقابة والأمان للعمليات',
        'fr_usage': ['Allez dans Admin > Audit.', 'Consultez les actions des différents utilisateurs.', 'Identifiez qui a créé, modifié ou supprimé un bon.'],
        'ar_usage': ['اذهب إلى الإدارة > سجل الرقابة.', 'راجع جميع الحركات والعمليات المسجلة باسم المستخدمين.', 'معرفة من قام بإنشاء، تعديل أو حذف أي فاتورة.'],
        'fr_example': 'Consulter le journal pour vérifier quel utilisateur a modifié le solde d\'un client hier soir.',
        'ar_example': 'مراجعة السجل لمعرفة المستخدم الذي قام بتعديل رصيد زبون ليلة أمس.'
    },
    '8-5': {
        'fr_title': '🪙 Configuration des symboles de devise (DA)',
        'ar_title': '🪙 ضبط العملة المحلية وتنسيق الأسعار',
        'fr_usage': ['Sélectionnez le symbole monétaire (par défaut DA).', 'Définissez le format d\'affichage des nombres.', 'Enregistrez pour appliquer sur les rapports.'],
        'ar_usage': ['حدد رمز العملة الوطنية (افتراضيًا دج).', 'اضبط شكل عرض وفواصل الأرقام المالية.', 'احفظ التعديل ليتم تطبيقه في الفواتير والتقارير.'],
        'fr_example': 'Changer le symbole pour afficher "DA" sur les documents officiels de vente.',
        'ar_example': 'ضبط تنسيق العملة ليظهر "دج" بجانب المبالغ في الفواتير والوصولات.'
    },
    '8-6': {
        'fr_title': '🔄 Réinitialisation complète de l\'application',
        'ar_title': '🔄 إعادة تهيئة البرنامج وتفريغ البيانات',
        'fr_usage': ['Allez dans Admin > Réinitialiser.', 'Cette action supprime TOUTES les données.', 'Confirmez avec le mot de passe administrateur.'],
        'ar_usage': ['اذهب إلى الإدارة > إعادة تهيئة التطبيق.', 'انتبه: هذا الإجراء يحذف جميع البيانات والعمليات.', 'أدخل كلمة مرور المدير للتأكيد والمسح.'],
        'fr_example': 'Vider la base de données de test pour démarrer l\'exploitation réelle de l\'application.',
        'ar_example': 'تفريغ قاعدة البيانات التجريبية لبدء العمل الفعلي وتسجيل المبيعات الحقيقية.'
    },
    '9-1': {
        'fr_title': '❓ Dépannage rapide des erreurs courantes',
        'ar_title': '❓ حلول سريعة لأهم المشاكل الشائعة',
        'fr_usage': ['Consultez la liste des erreurs connues.', 'Vérifiez l\'état de la connexion locale.', 'Suivez la procédure pas-à-pas pour résoudre.'],
        'ar_usage': ['راجع قائمة المشاكل والأعطال المعروفة.', 'تحقق من حالة الاتصال بالخادم المحلي.', 'اتبع خطوات الحل الموضحة لكل مشكلة.'],
        'fr_example': 'Si l\'application affiche "Erreur de connexion", vérifier que le serveur PostgreSQL est actif.',
        'ar_example': 'عند ظهور رسالة "خطأ في الاتصال"، تأكد من تشغيل خادم قاعدة البيانات PostgreSQL.'
    },
    '9-2': {
        'fr_title': '💬 Questions & Réponses fréquentes',
        'ar_title': '💬 الأسئلة الأكثر شيوعًا وإجاباتها',
        'fr_usage': ['Consultez les questions des autres utilisateurs.', 'Trouvez des conseils d\'utilisation avancés.', 'Apprenez à mieux utiliser Sabrina.'],
        'ar_usage': ['راجع أسئلة المستخدمين الآخرين وإجاباتها.', 'تعرف على نصائح متقدمة لتحسين العمل بالبرنامج.', 'تعلم كيفية صياغة أسئلتك للمساعدة سابرينا.'],
        'fr_example': 'Consulter la FAQ pour comprendre la différence entre un versement et un acompte.',
        'ar_example': 'مراجعة الأسئلة الشائعة لمعرفة الفرق المحاسبي بين الدفعة المالية والعربون.'
    },
    '9-3': {
        'fr_title': '⌨️ Liste complète des raccourcis clavier rapides',
        'ar_title': '⌨️ قائمة اختصارات لوحة المفاتيح الكاملة والسريعة',
        'fr_usage': [
            'Alt + ? ou Alt + / : Ouvrir ce Manuel d\'utilisation',
            'Alt + A : Accès rapide à la page d\'Ajout global',
            'Alt + S : Lancer une nouvelle Vente (Sale)',
            'Alt + B : Enregistrer un nouvel Achat (Buy)',
            'Alt + P : Enregistrer un nouveau Règlement / Versement (Payment)',
            'Alt + R : Lancer un nouvel ordre de Production / Recette',
            'Alt + D : Enregistrer une nouvelle Dépense annexe',
            'Alt + N : Ouvrir instantanément le Bloc-Notes',
            'Alt + M : Créer un nouveau client (Membre)',
            'Alt + F : Ajouter un nouveau Fournisseur',
            'Alt + K : Ajouter un nouveau produit au Catalogue',
            'Alt + O : Ouvrir le journal global des Opérations',
            'Alt + C : Ouvrir la gestion des Contacts',
            'Alt + X : Ouvrir le Dashboard des Rapports d\'activité',
            'Alt + H : Ouvrir l\'Historique des Bons et PDF',
            'Alt + U : Filtrer les contacts sur les Fournisseurs',
            'Alt + G : Ouvrir les Paramètres d\'administration (Gestion)',
            'Ctrl + S : Enregistrer / Soumettre le formulaire actif',
            'Ctrl + F : Placer le curseur sur le champ de recherche de la page',
            'Ctrl + K : Ouvrir la barre de recherche globale rapide'
        ],
        'ar_usage': [
            'Alt + ? أو Alt + / : فتح دليل الاستخدام هذا',
            'Alt + A : الانتقال لصفحة الإضافة السريعة العامة',
            'Alt + S : تسجيل بيع جديد',
            'Alt + B : تسجيل شراء جديد (مواد أولية/سلع)',
            'Alt + P : تسجيل دفعة مالية جديدة مقبوضة',
            'Alt + R : إطلاق عملية إنتاج جديدة',
            'Alt + D : تسجيل مصاريف أو تكاليف عامة جديدة',
            'Alt + N : فتح دفتر الملاحظات والمهام',
            'Alt + M : إضافة بطاقة زبون جديد',
            'Alt + F : إضافة مورد جديد للمؤسسة',
            'Alt + K : إضافة سلعة جديدة للدليل الفني',
            'Alt + O : الانتقال لسجل العمليات والمعاملات',
            'Alt + C : الانتقال لإدارة جهات الاتصال',
            'Alt + X : الانتقال لتقارير ومؤشرات الأداء',
            'Alt + H : الانتقال لأرشيف ومستندات الوصولات',
            'Alt + U : التصفية وعرض قائمة الموردين فقط',
            'Alt + G : فتح لوحة الإدارة والإعدادات العامة',
            'Ctrl + S : حفظ أو إرسال النموذج/الاستمارة النشطة',
            'Ctrl + F : التركيز على خانة البحث في الصفحة الحالية',
            'Ctrl + K : فتح شريط البحث الموحد والسريع'
        ],
        'fr_example': 'Appuyer sur Alt+S pour lancer un bon de vente sans toucher à la souris, puis Ctrl+S pour le valider.',
        'ar_example': 'اضغط على Alt+S لفتح استمارة بيع جديدة مباشرة دون استعمال الفأرة، ثم Ctrl+S لتأكيدها وحفظها.'
    },
    '9-4': {
        'fr_title': '📞 Support technique et informations de version',
        'ar_title': '📞 معلومات الإصدار وطلب الدعم الفني',
        'fr_usage': ['Consultez les informations de version active.', 'Notez le numéro de licence.', 'Contactez le support par téléphone ou email.'],
        'ar_usage': ['راجع رقم نسخة البرنامج الحالية المثبتة.', 'سجل رقم رخصة الاستخدام الخاصة بك.', 'اتصل بالدعم الفني عبر الهاتف أو البريد الإلكتروني.'],
        'fr_example': 'Vérifier que vous utilisez bien la dernière version stable de FABOuanes.',
        'ar_example': 'التأكد من استخدامك لآخر نسخة مستقرة ومحدثة من برنامج فاب وناس.'
    },
    '9-5': {
        'fr_title': '📱 Configuration rapide de l\'application mobile',
        'ar_title': '📱 دليل الإعداد السريع لتطبيق الهاتف',
        'fr_usage': ['Téléchargez l\'application mobile.', 'Scannez le QR Code de connexion.', 'Les données sont synchronisées automatiquement.'],
        'ar_usage': ['حمل تطبيق الهاتف المخصص للبرنامج.', 'امسح رمز QR للاتصال ومزامنة الحساب.', 'تتزامن فواتير المبيعات والزبائن تلقائيًا.'],
        'fr_example': 'Scanner le QR Code pour enregistrer des ventes directement depuis votre téléphone dans le hangar.',
        'ar_example': 'مسح رمز QR لتسجيل المبيعات من الهاتف الذكي مباشرة داخل المخزن.'
    },
    '9-6': {
        'fr_title': '📖 Lexique des termes comptables et techniques',
        'ar_title': '📖 قاموس المصطلحات المحاسبية والتقنية',
        'fr_usage': ['Consultez la définition des termes.', 'Comprenez ce qu\'est le PAMP ou le recalcul.', 'Lexique disponible en bilingue.'],
        'ar_usage': ['راجع معاني وتعاريف المصطلحات المستخدمة.', 'فهم معنى متوسط سعر الشراء أو الحساب التسلسلي.', 'قاموس المصطلحات متوفر باللغتين.'],
        'fr_example': 'Consulter la définition du PAMP (Prix d\'Achat Moyen Pondéré) pour mieux évaluer votre marge.',
        'ar_example': 'مراجعة مفهوم متوسط التكلفة لفهم كيفية تقييم أرباح وهوامش البيع.'
    }
}

def enrich_chapter_content(chapter_id: str, original_html: str) -> str:
    """Enrichit dynamiquement le code HTML original d'un chapitre du manuel

    avec des instructions détaillées et des exemples d'utilisation spécifiques à ce chapitre.
    """
    clean_id = chapter_id.strip()
    data = SPECIFIC_CHAPTER_DATA.get(clean_id, {
        'fr_title': f"💡 Guide d'utilisation - Chapitre {clean_id}",
        'ar_title': f"💡 دليل الاستخدام - الفصل {clean_id}",
        'fr_usage': ['Consultez les informations de ce chapitre.', 'Suivez les instructions à l\'écran.', 'Enregistrez les modifications.'],
        'ar_usage': ['راجع تفاصيل هذا الفصل بدقة.', 'اتبع التعليمات الموضحة في الشاشة.', 'احفظ التغييرات عند الانتهاء.'],
        'fr_example': 'Utilisation courante de l\'application au quotidien.',
        'ar_example': 'الاستخدام اليومي المعتاد للبرنامج.'
    })

    # 1. Extraction du contenu français et arabe d'origine
    fr_match = re.search(r'<div class="lang-fr">(.*?)</div>', original_html, re.DOTALL)
    ar_match = re.search(r'<div class="lang-ar"[^>]*>(.*?)</div>', original_html, re.DOTALL)

    fr_body = fr_match.group(1).strip() if fr_match else ""
    ar_body = ar_match.group(1).strip() if ar_match else ""

    # Nettoyage des titres h3 originaux pour éviter les doublons de titres
    fr_body = re.sub(r'<h3>.*?</h3>', '', fr_body)
    ar_body = re.sub(r'<h3.*?>.*?</h3>', '', ar_body)

    # 2. Génération du titre propre
    title_match_fr = re.search(r'<h3>(.*?)</h3>', original_html)
    title_match_ar = re.search(r'<h3.*?>((?:(?!<\/h3>).)*)<\/h3>', original_html)

    title_fr = title_match_fr.group(1).strip() if title_match_fr else f"Chapitre {clean_id}"
    title_ar = title_match_ar.group(1).strip() if title_match_ar else f"الفصل {clean_id}"

    # 3. Construction du contenu enrichi en Français
    fr_steps_li = "".join(f"<li class='mb-2'>{item}</li>" for item in data['fr_usage'])
    enriched_fr = f"""
    <div class="lang-fr">
        <h3>{title_fr}</h3>
        
        <div class="mb-4">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem;">
                <i class="bi bi-bookmark-fill me-2"></i>1. Présentation & Enjeux métier
            </h5>
            <p class="text-secondary mb-2" style="font-size: 0.85rem; line-height: 1.6;">
                La fonctionnalité <strong>"{data['fr_title']}"</strong> joue un rôle crucial dans le fonctionnement quotidien. 
                Elle permet d'assurer une traçabilité rigoureuse, de fiabiliser les calculs financiers complexes, et d'éviter les erreurs humaines d'écriture. 
                {fr_body if len(fr_body) > 30 else "Elle fournit un support opérationnel indispensable pour fluidifier les saisies et clarifier les comptes."}
            </p>
        </div>

        <div class="mb-4">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem;">
                <i class="bi bi-patch-check-fill me-2"></i>2. Instructions & Étapes d'exécution
            </h5>
            <p class="text-muted mb-2" style="font-size: 0.82rem;">Pour utiliser cette fonction efficacement, suivez ces étapes :</p>
            <ol class="ps-3 mb-2" style="font-size: 0.85rem; line-height: 1.65;">
                {fr_steps_li}
            </ol>
        </div>

        <div class="mb-4">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem;">
                <i class="bi bi-lightbulb-fill me-2"></i>3. Cas pratique d'utilisation réelle
            </h5>
            <div class="p-3 border rounded bg-light" style="font-size: 0.83rem; line-height: 1.5; border-left: 4px solid var(--system-blue, #2563eb) !important;">
                <strong>Scénario concret :</strong> {data['fr_example']}
            </div>
        </div>
    </div>
    """

    # 4. Construction du contenu enrichi en Arabe
    ar_steps_li = "".join(f"<li class='mb-2'>{item}</li>" for item in data['ar_usage'])
    enriched_ar = f"""
    <div class="lang-ar" dir="rtl" style="display:none; text-align: right;">
        <h3 style="border-bottom: 2px solid var(--system-blue, #2563eb); padding-bottom: 6px; font-family: 'Outfit', sans-serif;">{title_ar}</h3>
        
        <div class="mb-4" style="text-align: right;">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem; font-family: 'Outfit', sans-serif;">
                <i class="bi bi-bookmark-fill ms-2"></i>1. نظرة عامة والأهمية العملية
            </h5>
            <p class="text-secondary mb-2" style="font-size: 0.85rem; line-height: 1.6;">
                تعتبر ميزة <strong>"{data['ar_title']}"</strong> أداة أساسية في تنظيم سير العمل اليومي للمؤسسة.
                فهي تضمن الدقة المتناهية في الحسابات المالية وتمنع حدوث الأخطاء الناتجة عن الإدخال اليدوي العشوائي.
                {ar_body if len(ar_body) > 30 else "توفر هذه الميزة حلاً متكاملاً لتسريع تسجيل البيانات وضمان شفافية الحسابات للزبائن والموردين."}
            </p>
        </div>

        <div class="mb-4" style="text-align: right;">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem; font-family: 'Outfit', sans-serif;">
                <i class="bi bi-patch-check-fill ms-2"></i>2. الخطوات التفصيلية للاستخدام
            </h5>
            <p class="text-muted mb-2" style="font-size: 0.82rem;">لتحقيق أقصى استفادة من هذه الوظيفة، يرجى اتباع التعليمات التالية :</p>
            <ol class="pr-3 mb-2" style="font-size: 0.85rem; line-height: 1.65; padding-right: 18px;">
                {ar_steps_li}
            </ol>
        </div>

        <div class="mb-4" style="text-align: right;">
            <h5 class="fw-bold text-primary mb-2" style="font-size: 0.95rem; font-family: 'Outfit', sans-serif;">
                <i class="bi bi-lightbulb-fill ms-2"></i>3. مثال تطبيقي من واقع العمل
            </h5>
            <div class="p-3 border rounded bg-light" style="font-size: 0.83rem; line-height: 1.5; border-right: 4px solid var(--system-blue, #2563eb) !important; border-left: none; text-align: right;">
                <strong>سيناريو عملي :</strong> {data['ar_example']}
            </div>
        </div>
    </div>
    """

    # 5. Extraction des widgets interactifs d'origine s'ils existent
    widget_match = re.search(r'(<!-- Interactive Widget.*?</div>\s*</div>|<!-- Interactive Widget.*?-->.*?<div class="widget-wrapper.*?</div>\s*</div>)', original_html, re.DOTALL)
    widget_html = widget_match.group(1).strip() if widget_match else ""

    if not widget_html:
        clean_html = re.sub(r'<div class="lang-fr">.*?</div>', '', original_html, flags=re.DOTALL)
        clean_html = re.sub(r'<div class="lang-ar"[^>]*>.*?</div>', '', clean_html, flags=re.DOTALL)
        widget_html = clean_html.strip()

    return f"{enriched_fr}\n{enriched_ar}\n{widget_html}"


@router.get("/manual/chapter/{chapter_id}", response_class=HTMLResponse)
async def get_manual_chapter(chapter_id: str):
    """Serve a bilingual user manual chapter as HTML.
    
    Used for lazy-loading the 54 chapters to keep the initial page size low.
    """
    clean_id = chapter_id.strip()
    if clean_id not in MANUAL_CHAPTERS:
        raise HTTPException(status_code=404, detail="Chapitre introuvable")

    original_html = MANUAL_CHAPTERS[clean_id]
    # Enrich dynamically all 54 chapters with customized modular templates
    return enrich_chapter_content(clean_id, original_html)
