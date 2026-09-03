import type { CorpusSection } from "./types";

/**
 * Curated public-law excerpts for grounded RAG.
 * Texts are short working restatements of official English / Nepali provisions
 * (Constitution of Nepal 2015; National Civil Code 2074; Labour Act 2074;
 * Companies Act 2063; and related public statutes). Not a substitute for the
 * authentic gazette text.
 */
export const LEGAL_CORPUS: CorpusSection[] = [
  {
    id: "const-16",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "16",
    headingEn: "Right to live with dignity",
    headingNe: "सम्मानपूर्वक बाँच्न पाउने हक",
    textEn:
      "Every person shall have the right to live with dignity. No law shall be made providing for the death penalty to anyone.",
    textNe:
      "प्रत्येक व्यक्तिलाई सम्मानपूर्वक बाँच्न पाउने हक हुनेछ। कसैलाई पनि मृत्युदण्डको सजाय हुने गरी कुनै कानून बनाइने छैन।",
    tags: [
      "constitution",
      "dignity",
      "death penalty",
      "life",
      "संविधान",
      "सम्मान",
      "मृत्युदण्ड",
      "fundamental rights",
    ],
  },
  {
    id: "const-17",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "17",
    headingEn: "Right to freedom",
    headingNe: "स्वतन्त्रताको हक",
    textEn:
      "No person shall be deprived of personal liberty except in accordance with law. Every citizen shall have freedom of opinion and expression, peaceful assembly, form political parties, form unions, move and reside in any part of Nepal, and practise any profession or carry on any occupation, industry or trade, subject to the reasonable restrictions set out in the Constitution.",
    textNe:
      "कानूनबमोजिम बाहेक कुनै पनि व्यक्तिलाई वैयक्तिक स्वतन्त्रताबाट वञ्चित गरिने छैन। प्रत्येक नागरिकलाई विचार र अभिव्यक्तिको स्वतन्त्रता, शान्तिपूर्वक भेला हुने, दल खोल्ने, संघ संस्था खोल्ने, नेपालभर आवतजावत र बसोबास गर्ने तथा पेसा, रोजगार, उद्योग र व्यापार गर्ने स्वतन्त्रता हुनेछ।",
    tags: [
      "constitution",
      "freedom",
      "expression",
      "assembly",
      "स्वतन्त्रता",
      "अभिव्यक्ति",
      "fundamental rights",
    ],
  },
  {
    id: "const-18",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "18",
    headingEn: "Right to equality",
    headingNe: "समानताको हक",
    textEn:
      "All citizens shall be equal before law and no one shall be denied the equal protection of law. No discrimination shall be made in the application of general laws on grounds of origin, religion, race, caste, tribe, sex, physical condition, disability, health, marital status, pregnancy, economic condition, language, region, ideological conviction or similar grounds. Special laws for the protection or empowerment of disadvantaged groups are not treated as discrimination.",
    textNe:
      "सबै नागरिक कानूनको दृष्टिमा समान हुनेछन्। कसैलाई पनि कानूनको समान संरक्षणबाट वञ्चित गरिने छैन। उत्पत्ति, धर्म, वर्ण, जात, जाति, लिङ्ग, शारीरिक अवस्था, अपाङ्गता, स्वास्थ्य, वैवाहिक स्थिति, गर्भावस्था, आर्थिक अवस्था, भाषा, क्षेत्र, वैचारिक आस्था वा त्यस्तै आधारमा सामान्य कानूनको प्रयोगमा भेदभाव गरिने छैन।",
    tags: [
      "constitution",
      "equality",
      "discrimination",
      "समानता",
      "भेदभाव",
      "women",
      "caste",
      "fundamental rights",
    ],
  },
  {
    id: "const-20",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "20",
    headingEn: "Right to justice",
    headingNe: "न्याय सम्बन्धी हक",
    textEn:
      "No person shall be detained without being informed of the ground for such arrest. A person who is arrested has the right to consult a legal practitioner of choice and to be produced before the adjudicating authority within twenty-four hours of arrest, excluding time of travel. No person shall be punished for an act which was not punishable when committed, nor shall a heavier penalty be imposed than the one applicable at the time of the offence.",
    textNe:
      "पक्राउ परेको व्यक्तिलाई पक्राउको कारण नबताई थुनामा राखिने छैन। निजलाई आफूले रोजेको कानून व्यवसायीसँग सल्लाह गर्ने र यात्राको समयबाहेक चौबीस घण्टाभित्र न्यायिक अधिकारीसमक्ष उपस्थित गराइने हक हुनेछ। कुनै कार्य हुँदा सजाय नहुने भएमा पछि सजाय हुने गरी दण्डित गरिने छैन।",
    tags: [
      "constitution",
      "justice",
      "arrest",
      "lawyer",
      "24 hours",
      "न्याय",
      "पक्राउ",
      "वकिल",
    ],
  },
  {
    id: "const-22",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "22",
    headingEn: "Right against torture",
    headingNe: "यातना विरुद्धको हक",
    textEn:
      "No person who is detained during investigation, inquiry or trial or for any other reason shall be subjected to physical or mental torture or to cruel, inhuman or degrading treatment. Any such act is punishable by law and the victim has the right to obtain compensation.",
    textNe:
      "तथ्य अनुसन्धान, तहकिकात वा पुर्पक्षको सिलसिलामा वा अरू कुनै कारणले थुनामा रहेको व्यक्तिलाई शारीरिक वा मानसिक यातना दिइने वा निष्ठुर, अमानवीय वा अपमानजनक व्यवहार गरिने छैन। त्यस्तो कार्य कानूनद्वारा दण्डनीय हुनेछ र पीडितलाई क्षतिपूर्ति पाउने हक हुनेछ।",
    tags: ["constitution", "torture", "detention", "यातना", "क्षतिपूर्ति"],
  },
  {
    id: "const-31",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "31",
    headingEn: "Right to education",
    headingNe: "शिक्षा सम्बन्धी हक",
    textEn:
      "Every citizen shall have the right to access to basic education. Every citizen shall have the right to compulsory and free basic education, and to free education up to the secondary level from the State.",
    textNe:
      "प्रत्येक नागरिकलाई आधारभूत शिक्षामा पहुँचको हक हुनेछ। प्रत्येक नागरिकलाई राज्यबाट आधारभूत तहसम्मको शिक्षा अनिवार्य र निःशुल्क तथा माध्यमिक तहसम्मको शिक्षा निःशुल्क पाउने हक हुनेछ।",
    tags: ["constitution", "education", "school", "शिक्षा", "निःशुल्क"],
  },
  {
    id: "const-38",
    actTitleEn: "Constitution of Nepal",
    actTitleNe: "नेपालको संविधान",
    actYearBs: "2072",
    actYearAd: "2015",
    sectionNumber: "38",
    headingEn: "Rights of women",
    headingNe: "महिलाको हक",
    textEn:
      "Every woman shall have equal lineage right without gender-based discrimination. Women shall have the right to safe motherhood and reproductive health, to participate in all organs of the State on the basis of proportional inclusion, and special opportunity in education, health, employment and social security. No woman shall be subjected to physical, mental, sexual, psychological or other form of violence or exploitation, and such an act is punishable by law with a right to compensation.",
    textNe:
      "प्रत्येक महिलालाई लैङ्गिक भेदभाव बिना समान वंशीय हक हुनेछ। महिलालाई सुरक्षित मातृत्व र प्रजनन स्वास्थ्य, समानुपातिक समावेशी सिद्धान्तका आधारमा राज्यका सबै निकायमा सहभागिता तथा शिक्षा, स्वास्थ्य, रोजगारी र सामाजिक सुरक्षामा विशेष अवसरको हक हुनेछ। कुनै पनि महिलालाई शारीरिक, मानसिक, यौनजन्य, मनोवैज्ञानिक वा अन्य हिंसा वा शोषण गरिने छैन।",
    tags: [
      "constitution",
      "women",
      "lineage",
      "inheritance",
      "violence",
      "महिला",
      "वंशीय",
      "हिंसा",
    ],
  },
  {
    id: "civil-67",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "67",
    headingEn: "Marriage deemed to be concluded",
    headingNe: "विवाह भएको मानिने",
    textEn:
      "Marriage is a permanent, inviolable, holy and social bond between a man and a woman based on free consent, and it is deemed concluded when the conditions of this Chapter are fulfilled.",
    textNe:
      "विवाह पुरुष र महिलाबीच स्वतन्त्र सहमतिमा आधारित स्थायी, अविच्छेद्य, पवित्र र सामाजिक सम्बन्ध हो। यस परिच्छेदबमोजिमका शर्त पूरा भएपछि विवाह भएको मानिन्छ।",
    tags: ["civil", "marriage", "family", "विवाह", "देवानी"],
  },
  {
    id: "civil-70",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "70",
    headingEn: "Marriage may be concluded",
    headingNe: "विवाह गर्न सकिने",
    textEn:
      "Subject to this Chapter, a marriage may be concluded between a man and a woman if they agree to accept each other as husband and wife, are not relatives punishable for incest, neither already has a subsisting matrimonial relationship, and both have attained twenty years of age. Customary marriages within a relationship permitted by the ethnic community or clan are not barred by the incest clause.",
    textNe:
      "यस परिच्छेदबमोजिम पुरुष र महिलाबीच विवाह गर्न सकिन्छ यदि दुवै एकार्कालाई पतिपत्नीको रूपमा स्वीकार गर्न सहमत छन्, हाडनाता करणीमा सजाय हुने नाताका होइनन्, दुवैको विद्यमान वैवाहिक सम्बन्ध छैन, र दुवैले बीस वर्ष उमेर पूरा गरेका छन्।",
    tags: [
      "civil",
      "marriage",
      "age",
      "20",
      "twenty",
      "consent",
      "विवाह",
      "उमेर",
      "बीस",
      "२०",
    ],
  },
  {
    id: "civil-71",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "71",
    headingEn: "Marriage not to be concluded",
    headingNe: "विवाह गर्न नहुने",
    textEn:
      "A marriage shall not be concluded if either person is already married, if the parties are within a prohibited degree of relationship, if either has not attained twenty years of age, or if consent is obtained by coercion, undue influence, mistake or fraud.",
    textNe:
      "कुनै पक्षको पहिलेको विवाह कायम रहेमा, निषेधित नाताभित्र परेमा, बीस वर्ष उमेर पूरा नगरेमा, वा करकाप, अनुचित प्रभाव, भूल वा ठगीबाट सहमति लिइएमा विवाह गर्न हुँदैन।",
    tags: ["civil", "marriage", "void", "coercion", "polygamy", "विवाह", "बहुविवाह"],
  },
  {
    id: "civil-76",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "76",
    headingEn: "Marriage to be registered",
    headingNe: "विवाह दर्ता गर्नुपर्ने",
    textEn:
      "A marriage concluded pursuant to this Chapter shall be registered. Registration of marriage is the legal record used to prove the marital relationship for subsequent civil claims.",
    textNe:
      "यस परिच्छेदबमोजिम भएको विवाह दर्ता गर्नुपर्नेछ। विवाह दर्ता पछिल्ला देवानी दाबीका लागि वैवाहिक सम्बन्ध प्रमाणित गर्ने कानुनी अभिलेख हो।",
    tags: ["civil", "marriage", "registration", "विवाह", "दर्ता"],
  },
  {
    id: "civil-93",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "93",
    headingEn: "Divorce by mutual consent",
    headingNe: "आपसी सहमतिमा सम्बन्धविच्छेद",
    textEn:
      "Husband and wife may obtain a divorce by mutual consent in accordance with the procedure set out in this Chapter. Mutual-consent divorce does not require proof of a fault ground once both spouses freely agree to dissolve the marriage.",
    textNe:
      "पति र पत्नीले यस परिच्छेदबमोजिमको प्रक्रिया अपनाई आपसी सहमतिमा सम्बन्धविच्छेद गर्न सक्नेछन्। दुवैको स्वतन्त्र सहमति भएपछि दोष प्रमाणित गर्नु पर्दैन।",
    tags: ["civil", "divorce", "mutual consent", "सम्बन्धविच्छेद", "सहमति"],
  },
  {
    id: "civil-95",
    actTitleEn: "National Civil Code, 2074",
    actTitleNe: "राष्ट्रिय देवानी संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "95",
    headingEn: "Divorce on specified grounds",
    headingNe: "तोकिएका आधारमा सम्बन्धविच्छेद",
    textEn:
      "A spouse may seek divorce on the grounds specified in this Section, including circumstances such as living separately, cruelty, or other statutory grounds. The wife may also seek divorce where the husband has committed rape against her.",
    textNe:
      "यस दफामा तोकिएका आधारमा पति वा पत्नीले सम्बन्धविच्छेदको माग गर्न सक्नेछन्, जसमा अलग बसोबास, क्रुर व्यवहार लगायतका कानुनी आधार पर्दछन्। पतिले पत्नीमाथि जबरजस्ती करणी गरेमा पत्नीले सम्बन्धविच्छेद माग गर्न सक्नेछिन्।",
    tags: ["civil", "divorce", "cruelty", "marital rape", "सम्बन्धविच्छेद", "जबरजस्ती"],
  },
  {
    id: "labour-28",
    actTitleEn: "Labour Act, 2074",
    actTitleNe: "श्रम ऐन, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "28",
    headingEn: "Working hours",
    headingNe: "काम गर्ने समय",
    textEn:
      "No employer shall employ a labour to work more than eight hours a day and forty-eight hours a week. Labours shall be provided with half an hour of rest after five hours of continuous work. Rest time is counted within the working hours.",
    textNe:
      "कुनै पनि रोजगारदाताले श्रमिकलाई एक दिनमा आठ घण्टा र एक हप्तामा अठचालीस घण्टाभन्दा बढी काममा लगाउनु हुँदैन। निरन्तर पाँच घण्टा काम गरेपछि आधा घण्टा विश्राम दिनुपर्नेछ। विश्रामको समय काम गर्ने समयभित्र गणना गरिन्छ।",
    tags: [
      "labour",
      "hours",
      "overtime",
      "8",
      "48",
      "work",
      "श्रम",
      "घण्टा",
      "आठ",
      "employment",
    ],
  },
  {
    id: "labour-30",
    actTitleEn: "Labour Act, 2074",
    actTitleNe: "श्रम ऐन, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "30",
    headingEn: "Overtime work",
    headingNe: "अतिरिक्त समयको काम",
    textEn:
      "An employer may cause a labour to work overtime if the nature of the work so requires. Overtime shall not exceed four hours a day and twenty-four hours a week. Overtime remuneration shall be paid at one and one-half times the ordinary rate of remuneration.",
    textNe:
      "कामको प्रकृतिले आवश्यक परेमा रोजगारदाताले श्रमिकलाई अतिरिक्त समय काममा लगाउन सक्नेछ। अतिरिक्त समय एक दिनमा चार घण्टा र एक हप्तामा चौबीस घण्टाभन्दा बढी हुने छैन। अतिरिक्त समयको पारिश्रमिक सामान्य दरको डेढ गुणा दिनुपर्नेछ।",
    tags: [
      "labour",
      "overtime",
      "hours",
      "1.5",
      "wage",
      "श्रम",
      "अतिरिक्त",
      "पारिश्रमिक",
    ],
  },
  {
    id: "company-3",
    actTitleEn: "Companies Act, 2063",
    actTitleNe: "कम्पनी ऐन, २०६३",
    actYearBs: "2063",
    actYearAd: "2006",
    sectionNumber: "3",
    headingEn: "Incorporation of company",
    headingNe: "कम्पनीको स्थापना",
    textEn:
      "Any person desirous of undertaking an enterprise with a profit motive may, either singly or jointly with others, incorporate a company for the objectives set forth in the memorandum of association. There shall be a minimum of seven promoters for the incorporation of a public company, except where a public company incorporates another public company. A company not distributing profits may also be incorporated subject to Chapter-19.",
    textNe:
      "नाफाको उद्देश्यले उद्यम गर्न चाहने कुनै व्यक्ति एक्लै वा अरूसँग मिली प्रबन्धपत्रमा उल्लिखित उद्देश्यका लागि कम्पनी स्थापना गर्न सक्नेछ। सार्वजनिक कम्पनी स्थापना गर्न न्यूनतम सातजना प्रवर्द्धक चाहिन्छ। मुनाफा वितरण नगर्ने कम्पनी पनि परिच्छेद-१९ बमोजिम स्थापना गर्न सकिन्छ।",
    tags: [
      "company",
      "incorporation",
      "public",
      "private",
      "promoters",
      "seven",
      "कम्पनी",
      "स्थापना",
      "सार्वजनिक",
    ],
  },
  {
    id: "penal-177",
    actTitleEn: "National Penal Code, 2074",
    actTitleNe: "राष्ट्रिय अपराध संहिता, २०७४",
    actYearBs: "2074",
    actYearAd: "2017",
    sectionNumber: "177",
    headingEn: "Murder",
    headingNe: "ज्यान मार्ने",
    textEn:
      "A person who, with the intention of causing death, causes the death of another person commits murder. Murder is a serious offence punishable under this Code, and the Constitution separately forbids making any law that provides for the death penalty.",
    textNe:
      "मृत्यु गराउने नियतले अरूको ज्यान लिने व्यक्तिले ज्यान मार्ने कसुर गरेको मानिन्छ। यो संहिताअन्तर्गत गम्भीर कसुर हो। संविधानले मृत्युदण्डको सजाय हुने गरी कानून बनाउन निषेध गरेको छ।",
    tags: ["penal", "murder", "homicide", "death", "ज्यान", "हत्या", "अपराध"],
  },
  {
    id: "eta-3",
    actTitleEn: "Electronic Transactions Act, 2063",
    actTitleNe: "विद्युतीय कारोबार ऐन, २०६३",
    actYearBs: "2063",
    actYearAd: "2006",
    sectionNumber: "3",
    headingEn: "Legal recognition of electronic records",
    headingNe: "विद्युतीय रेकर्डको कानुनी मान्यता",
    textEn:
      "Where any law requires information to be in writing, that requirement is satisfied if the information is rendered or made available in an electronic form and is accessible so as to be usable for subsequent reference.",
    textNe:
      "कुनै कानूनले जानकारी लिखित रूपमा हुनुपर्ने व्यवस्था गरेको भए पनि त्यो जानकारी विद्युतीय रूपमा उपलब्ध गराइएको र पछि प्रयोग गर्न सकिने गरी पहुँचयोग्य भएमा सो आवश्यकता पूरा भएको मानिन्छ।",
    tags: [
      "electronic",
      "digital",
      "record",
      "writing",
      "cyber",
      "विद्युतीय",
      "रेकर्ड",
    ],
  },
  {
    id: "rti-3",
    actTitleEn: "Right to Information Act, 2064",
    actTitleNe: "सूचनाको हकसम्बन्धी ऐन, २०६४",
    actYearBs: "2064",
    actYearAd: "2007",
    sectionNumber: "3",
    headingEn: "Right to information",
    headingNe: "सूचनाको हक",
    textEn:
      "Every Nepali citizen shall have the right to information subject to this Act. Public agencies have a corresponding duty to provide information that is not protected by a statutory exemption.",
    textNe:
      "प्रत्येक नेपाली नागरिकलाई यस ऐनबमोजिम सूचनाको हक हुनेछ। सार्वजनिक निकायको कर्तव्य हुनेछ—कानूनी अपवादमा नपरेको सूचना उपलब्ध गराउनु।",
    tags: ["rti", "information", "citizen", "transparency", "सूचना", "नागरिक"],
  },
  {
    id: "consumer-3",
    actTitleEn: "Consumer Protection Act, 2075",
    actTitleNe: "उपभोक्ता संरक्षण ऐन, २०७५",
    actYearBs: "2075",
    actYearAd: "2018",
    sectionNumber: "3",
    headingEn: "Rights of consumers",
    headingNe: "उपभोक्ताका हक",
    textEn:
      "Every consumer shall have the rights specified in this Act, including the right to be protected from the sale and supply of goods or services that may cause harm to life, body, health or property; the right to be informed about quality, quantity, price and purity; the right to choose; and the right to be heard and to obtain compensation for harm caused by goods or services.",
    textNe:
      "प्रत्येक उपभोक्तालाई जीवन, शरीर, स्वास्थ्य वा सम्पत्तिमा हानि पुर्‍याउन सक्ने वस्तु वा सेवाबाट संरक्षण पाउने, गुण, परिमाण, मूल्य र शुद्धताबारे जानकारी पाउने, रोज्ने, सुनुवाइ पाउने र हानिका लागि क्षतिपूर्ति पाउने हक हुनेछ।",
    tags: [
      "consumer",
      "goods",
      "services",
      "compensation",
      "उपभोक्ता",
      "क्षतिपूर्ति",
    ],
  },
];
