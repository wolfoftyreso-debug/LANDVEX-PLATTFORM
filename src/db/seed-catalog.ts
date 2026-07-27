/**
 * Baltic Bridge catalog (46 profiles: LT, LV, EE, PL) — imported as UNCLAIMED.
 *
 * Batch 2 (2026-07): 10 Polish + 3 Latvian + 3 Estonian companies added, and
 * 28 existing profiles enriched with publicly stated certifications (ISO
 * 3834, EN 1090 incl. EXC classes, ISO 9001/14001/45001, EN 15085, ASME…)
 * and business awards (Diamenty Forbesa, Gazele Biznesu). Research was done
 * against public web sources; certificates/awards are recorded ONLY where
 * the cited page states them, and remain clearly self-reported on profiles.
 * NOTE: facts were extracted via search-engine renderings of the cited
 * pages (direct fetch was unavailable) — the pre-launch manual source check
 * in the backlog covers re-verifying each citation.
 *
 * Data policy (per the catalog brief):
 * - Only facts published on open, public sources (B2B directories, EU
 *   partnering portals, the companies' own public pages). Source URL is
 *   stored on every profile and shown publicly for attribution.
 * - No personal contact data (GDPR): the public website is the contact path.
 * - No logos or images — none are licensed for reuse.
 * - Every profile is claimable: the company takes it over via the claim
 *   flow, reviewed by ops; verification (the badge) is a separate process
 *   and is NEVER granted by import.
 *
 * Descriptions paraphrase the sources; where a fact (city, founding year)
 * was not stated by the source it is left empty rather than guessed.
 */
import { eq } from "drizzle-orm";
import { db, pool } from "@/lib/db";
import { logger } from "@/lib/logger";
import { users } from "@/modules/identity/schema";
import { companies, companySlugs } from "@/modules/companies/schema";
import { slugify } from "@/modules/companies/service";
import { writeAudit, appendOutbox } from "@/modules/audit/service";

interface CatalogEntry {
  name: string;
  country: "LT" | "LV" | "EE" | "PL";
  city?: string;
  category: string;
  description: string;
  website?: string;
  yearFounded?: number;
  /** Only certifications/awards explicitly stated on the cited source page */
  certifications?: string[];
  awards?: string[];
  sourceUrl: string;
  sourceName: string;
}

/** Facts found later for companies already imported — applied as updates */
interface CatalogEnrichment {
  name: string;
  certifications?: string[];
  awards?: string[];
  city?: string;
  yearFounded?: number;
  website?: string;
  sourceUrl: string;
  sourceName: string;
}

const WELD = "Welding & metal fabrication";
const PIPE = "Industrial piping & installation";
const CNC = "CNC machining";
const MARINE = "Shipbuilding & marine";
const STEEL = "Steel structures";
const STAINLESS = "Stainless equipment";

const CATALOG: CatalogEntry[] = [
  // ------------------------------------------------------------ Lithuania
  { name: "Westa Steel UAB", country: "LT", category: PIPE,
    description: "Pipe welding, installation, reconstruction and repair of steel parts and equipment. Subcontractor to major Lithuanian and foreign petrochemical, food-industry, pharmaceutical, construction and shipping companies.",
    website: "https://www.westasteel.lt", sourceUrl: "https://www.westasteel.lt/en/about-us/", sourceName: "westasteel.lt (company site)" },
  { name: "Rokvelas UAB", country: "LT", category: WELD,
    description: "Metal working services for small-serial and serial production, with over a decade of export experience.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/steel-and-metal-fabrication.html", sourceName: "Europages" },
  { name: "Bermetix UAB", country: "LT", city: "Vilnius", category: STAINLESS,
    description: "European manufacturer of custom stainless steel tanks and process vessels.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/welding.html", sourceName: "Europages" },
  { name: "Lavango Engineering LT UAB", country: "LT", category: STAINLESS,
    description: "Manufactures stainless steel equipment for the food industry.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Anvalda UAB", country: "LT", category: WELD,
    description: "Metal processing company with over 19 years of experience; services include TIG, MIG and MAG welding.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "KELLA Engineering", country: "LT", category: WELD,
    description: "Metal fabrication services specializing in outsourced fabrication work.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/welding%20work%20-%20steels%20and%20metal.html", sourceName: "Europages" },
  { name: "GRR Engineering UAB", country: "LT", category: WELD,
    description: "Manufactures industrial heat-treatment equipment and provides metal working services.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Stansefabrikken Automotive UAB", country: "LT", yearFounded: 2008, category: WELD,
    description: "Established in Lithuania in 2008; specializes in stamping, automatic welding and Tier 2 automotive supply.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Martema UAB", country: "LT", yearFounded: 2004, category: WELD,
    description: "Metal processing and construction manufacturing services in Lithuania and across Europe since 2004.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "OSS UAB", country: "LT", category: PIPE,
    description: "Industrial piping installation and welding. Active in 15 countries over two decades, with representative offices in Sweden, Finland and Norway.",
    website: "https://www.oss.lt", sourceUrl: "https://www.oss.lt/", sourceName: "oss.lt (company site)" },
  { name: "Kijora UAB", country: "LT", yearFounded: 2014, category: PIPE,
    description: "Piping systems manufacturing and installation since 2014: welders, pipe fitters and plumbers executing plumbing, welding, pipeline installation and metal work to EU requirements.",
    website: "https://kijora.lt", sourceUrl: "https://kijora.lt/en/", sourceName: "kijora.lt (company site)" },
  { name: "Feliuga UAB", country: "LT", yearFounded: 2001, category: PIPE,
    description: "Prefabrication of pipe spools and piping components for power, petrochemical, paper-cellulose, offshore and shipbuilding projects since 2001.",
    sourceUrl: "https://www.copiermachinery.com/en/about-us/case-studies/feliuga-uab-increased-productivity-by-400/", sourceName: "Copier Machinery case study" },
  { name: "Western Baltija Shipbuilding UAB", country: "LT", city: "Klaipėda", category: MARINE,
    description: "Shipbuilding company with 70+ years of heritage and more than 600 employees, part of the Western Shipyard Group in Klaipėda.",
    website: "https://wbs.lt", sourceUrl: "https://wbs.lt/en/", sourceName: "wbs.lt (company site)" },
  { name: "Marine Technology (Western Shipyard Group)", country: "LT", city: "Klaipėda", category: MARINE,
    description: "Engineering, manufacturing and maintenance of complex structural steel components and cable-handling solutions for offshore energy, oil and gas; investing in robotic welding capacity at Klaipėda Seaport.",
    sourceUrl: "https://investlithuania.com/news/marine-technology-to-invest-e15m-in-advanced-manufacturing-expansion-in-klaipeda/", sourceName: "Invest Lithuania" },
  // -------------------------------------------------------------- Latvia
  { name: "Ritausmas Steel Constructions SIA", country: "LV", city: "Riga", yearFounded: 2013, category: STEEL,
    description: "Metal fabrication partner operating a 6 000 m² facility in Riga: laser and plasma cutting, sheet metal bending and certified steel structures to EN 3834 and EN 1090. Customers across Latvia and the Nordics.",
    website: "https://ritausmas.lv", sourceUrl: "https://ritausmas.lv/en/", sourceName: "ritausmas.lv (company site)" },
  { name: "Industrial Welding SIA", country: "LV", category: WELD,
    description: "Metal product manufacturer, part of a holding group with 25 years of experience.",
    sourceUrl: "https://www.emis.com/php/company-profile/LV/Industrial_Welding_SIA_en_9994966.html", sourceName: "EMIS company profile" },
  { name: "EMJ Metals SIA", country: "LV", category: WELD,
    description: "Metalworking, sheet metal processing and fabrication.",
    website: "https://www.emjmetals.lv", sourceUrl: "https://www.emjmetals.lv/", sourceName: "emjmetals.lv (company site)" },
  { name: "Metal Constructions (metals.lv)", country: "LV", category: STEEL,
    description: "Latvian manufacturer of metal constructions.",
    website: "https://metals.lv", sourceUrl: "https://metals.lv/en/", sourceName: "metals.lv (company site)" },
  { name: "CNC Latvia Ltd", country: "LV", city: "Riga", yearFounded: 2013, category: CNC,
    description: "Precision CNC turning and milling since 2013, exporting mainly to customers in Sweden, Norway and Finland.",
    website: "https://cnclatvia.com", sourceUrl: "https://cnclatvia.com/", sourceName: "cnclatvia.com (company site)" },
  { name: "Energoimpex Metal", country: "LV", city: "Ventspils", category: CNC,
    description: "Export-oriented CNC machining with 11 CNC machines, positioned near the Freeport of Ventspils.",
    sourceUrl: "https://metal.energoimpex.eu/cnc-machining/", sourceName: "energoimpex.eu (company site)" },
  { name: "Metalmeistars Ltd", country: "LV", yearFounded: 1998, category: WELD,
    description: "Latvian family business founded in 1998, providing precision metalworking in the Baltic states.",
    website: "https://www.metal.lv", sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  { name: "AB Metal Ltd", country: "LV", yearFounded: 2005, category: WELD,
    description: "Founded in 2005 within the Metalmeistars family of companies to develop export-market operations.",
    sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  // ------------------------------------------------------------- Estonia
  { name: "AGMA OÜ", country: "EE", city: "Tallinn", yearFounded: 2011, category: WELD,
    description: "Precision metal fabrication for demanding sectors: high-integrity metal structures for offshore, gas, oil, engineering and construction. 20–49 employees.",
    sourceUrl: "https://www.europages.co.uk/AGMA/00000003878045-298430001.html", sourceName: "Europages" },
  { name: "Monik OÜ", country: "EE", city: "Tallinn", category: STEEL,
    description: "Installation of metal structures in Estonia and Scandinavia; workshops equipped for welding, plasma cutting, forming and rolling in carbon, high-alloy and aluminium steels.",
    website: "https://www.monik.ee", sourceUrl: "https://www.monik.ee/", sourceName: "monik.ee (company site)" },
  { name: "Bernal Estonia OÜ", country: "EE", category: WELD,
    description: "Estonian metal fabrication company — \"let's create metal possibilities\".",
    website: "https://bernal.ee", sourceUrl: "https://bernal.ee/en/", sourceName: "bernal.ee (company site)" },
  { name: "Steel Element OÜ", country: "EE", city: "Tallinn", yearFounded: 2018, category: STEEL,
    description: "Steel fabrication with a capacity of 300 tonnes per month; installation services across Estonia, Scandinavia and Europe.",
    website: "https://steelelement.ee", sourceUrl: "https://steelelement.ee/en/", sourceName: "steelelement.ee (company site)" },
  { name: "Metalset OÜ", country: "EE", category: PIPE,
    description: "Prefabrication and installation of industrial pipelines and steel structures up to EXC3; approved supplier at several European companies.",
    website: "https://metalset.eu", sourceUrl: "https://metalset.eu/", sourceName: "metalset.eu (company site)" },
  { name: "Levstal Group", country: "EE", category: STEEL,
    description: "Metal engineering and steel fabrication, delivering structures to clients in Finland, Germany, Norway, Sweden, Austria, Italy and beyond.",
    website: "https://levstal.com", sourceUrl: "https://levstal.com/", sourceName: "levstal.com (company site)" },
  { name: "Scanweld AS", country: "EE", category: PIPE,
    description: "Fabrication and installation as core competences within industrial piping and steel work.",
    website: "https://www.scanweld.ee", sourceUrl: "https://www.scanweld.ee/core-competence/our-core-competence/fabrication-installation/", sourceName: "scanweld.ee (company site)" },
  { name: "Radius Machining OÜ", country: "EE", city: "Tallinn", category: CNC,
    description: "Serial CNC turning and milling for two decades, from mechanical engineering to aerospace, with sites in Tallinn, Tartu and Pärnu serving Scandinavian and Central European customers.",
    sourceUrl: "https://estonianexport.ee/directory/listing/radius-machining-ou/", sourceName: "Estonian Export Directory" },
  { name: "Estanc AS", country: "EE", city: "Rae, Harju County", yearFounded: 1992, category: STAINLESS,
    description: "Family-owned manufacturer of process equipment, tanks and pressure vessels in carbon and stainless steel, founded in 1992, with a 10,500 m² production complex near Tallinn where carbon and stainless steel production are separated.",
    website: "https://estanc.eu",
    certifications: ["ISO 9001", "ISO 3834-2", "EN 1090", "DNV GL Class I & II", "ASME U", "ASME U2"],
    sourceUrl: "https://estanc.eu/certificates/", sourceName: "estanc.eu (company site)" },
  { name: "Polinord OÜ", country: "EE", city: "Maardu", yearFounded: 2006, category: WELD,
    description: "Medium-sized mechanical engineering and metalworking company founded in 2006 that designs, manufactures and installs metal structures for construction and mechanical engineering in Estonia and abroad; certified to EN 1090-2 EXC2 and ISO 3834-3 since 2014.",
    website: "https://polinord.ee",
    certifications: ["EN 1090-2 EXC2", "ISO 3834-3"],
    sourceUrl: "https://polinord.ee/en/", sourceName: "polinord.ee (company site)" },
  { name: "HANZA Mechanics Tartu AS", country: "EE", city: "Vahi, Tartu County", category: CNC,
    description: "Contract manufacturer in the Swedish HANZA group offering CNC turning and 4- and 5-axis milling in steel, stainless steel, aluminium, brass and plastics, together with sheet metal work, cable harness and assembly services.",
    website: "https://hanza.com/manufacturing-clusters/cluster-baltics/hanza-mechanics-tartu/",
    certifications: ["ISO 9001", "ISO 14001", "ISO 45001", "ISO 3834-2"],
    sourceUrl: "https://estonianexport.ee/directory/listing/hanza-mechanics-tartu-as/", sourceName: "Estonian Export Directory" },
  // -------------------------------------------------------- Latvia (batch 2)
  { name: "MetUp SIA", country: "LV", city: "Ventspils", category: STEEL,
    description: "Certified steel fabricator in Ventspils providing steel structure fabrication, welding and CNC machining for construction and industrial clients in the Baltics, Scandinavia and Central and Western Europe, with controlled welding procedures, NDT inspection and CE-marked delivery.",
    website: "https://www.metup.lv",
    certifications: ["EN 1090-2 EXC2", "ISO 9001"],
    sourceUrl: "https://www.metup.lv/certifications", sourceName: "metup.lv (company site)" },
  { name: "East Metal SIA", country: "LV", city: "Daugavpils", category: WELD,
    description: "Danish-owned metal fabrication company with its main manufacturing in three Latvian factories, including Daugavpils and Dobele, specializing in welded metal products in steel, stainless steel and aluminium.",
    website: "https://www.eastmetal.com",
    certifications: ["ISO 9001", "ISO 3834-2", "EN 1090", "EN 15085-2"],
    sourceUrl: "https://www.eastmetal.com/en/competences/certificates-2/", sourceName: "eastmetal.com (company site)" },
  { name: "UPB AS", country: "LV", city: "Liepāja", category: STEEL,
    description: "Latvian engineering and manufacturing group with factories and offices in Liepāja, Riga, Grobiņa and Daugavpils, producing and installing steel, precast concrete and glazed structures for export markets; group companies certified to ISO 9001/14001/45001 since 2000, with NORSOK-compliant products and CE marking.",
    website: "https://www.upb.lv",
    certifications: ["ISO 9001", "ISO 14001", "ISO 45001"],
    sourceUrl: "https://www.upb.lv/en/sustainability/quality", sourceName: "upb.lv (company site)" },
  // -------------------------------------------------------------- Poland
  { name: "Weldon Sp. z o.o.", country: "PL", category: STEEL,
    description: "Polish manufacturer of steel structures, noise barriers, electricity pylons, modular buildings and containers, with over 20 years of industrial experience across Europe. Welding quality system certified to PN-EN ISO 3834-2 and factory production control to PN-EN 1090 up to execution class EXC3.",
    website: "https://weldon.eu",
    certifications: ["ISO 9001:2015", "ISO 14001:2015", "ISO 45001:2018", "AQAP 2110:2016", "PN-EN ISO 3834-2:2021", "PN-EN 1090-1+A1:2012", "PN-EN 1090-2:2018 (EXC3)"],
    sourceUrl: "https://weldon.eu/", sourceName: "weldon.eu (company site)" },
  { name: "KBR Poland", country: "PL", city: "Kwidzyn", yearFounded: 1994, category: WELD,
    description: "Industrial services enterprise on the European market since 1994: maintenance, installations and start-ups, plus fabrication of industrial equipment. Steel structures manufactured to PN-EN 1090-1 and PN-EN ISO 3834-2; IWE/EWE-certified welding supervisors, 100+ qualified welding procedures (WPQR) and an in-house welding school.",
    website: "https://www.kbr-poland.com",
    certifications: ["PN-EN 1090-1", "PN-EN ISO 3834-2"],
    sourceUrl: "https://www.kbr-poland.com/en/steel-structures", sourceName: "kbr-poland.com (company site)" },
  { name: "Elektron Sp. z o.o.", country: "PL", yearFounded: 2018, category: WELD,
    description: "Metal processing company in the Podkarpackie region offering laser cutting, sheet metal bending, pipe and profile bending, MIG/MAG/TIG welding and powder coating in a facility of over 3,500 m² with more than 100 specialists.",
    website: "https://webelektron.com",
    certifications: ["ISO 9001", "ISO 3834", "EN 1090 EXC3"],
    sourceUrl: "https://webelektron.com/about-us/", sourceName: "webelektron.com (company site)" },
  { name: "BUD-INVEST Steel", country: "PL", city: "Tczew", category: PIPE,
    description: "Designs, prefabricates and installs steel structures, industrial pipelines and pressure vessels from its own facility in Tczew, with workshop prefabrication and on-site assembly for chemical, petrochemical, energy, offshore and shipbuilding customers in Poland and Germany.",
    website: "https://budinvest-steel.com",
    certifications: ["EN 1090", "EN ISO 3834"],
    sourceUrl: "https://budinvest-steel.com/en/about", sourceName: "budinvest-steel.com (company site)" },
  { name: "HML Nosewicz", country: "PL", city: "Lidzbark Warmiński", category: STAINLESS,
    description: "Manufacturer of stainless and carbon steel pressure and non-pressure tanks, reactors, industrial mixers and heat exchangers for the pharmaceutical, cosmetics, food, energy and chemical industries, with conformity certificates from notified bodies (UDT, TÜV) for pressure equipment.",
    website: "https://hmlnosewicz.pl",
    certifications: ["ISO 9001:2015", "ISO 3834-2:2005", "ASME Sec VIII div 1", "U-Stamp"],
    sourceUrl: "https://hmlnosewicz.pl/en/quality-control/", sourceName: "hmlnosewicz.pl (company site)" },
  { name: "Radmot Sp. z o.o.", country: "PL", city: "Jedlińsk", category: CNC,
    description: "CNC turning and milling subcontractor with over 40 years of experience, operating close to 90 CNC machine tools with more than 200 employees and 22 measuring machines guaranteeing accuracy to 0.005 mm, serving automotive, electrical and mechanical engineering industries.",
    website: "https://radmot.com",
    certifications: ["ISO 9001:2015", "IATF 16949", "ISO 14001:2015"],
    sourceUrl: "https://radmot.com/cnc-company", sourceName: "radmot.com (company site)" },
  { name: "CNC ALFA", country: "PL", city: "Radom", category: CNC,
    description: "Family-owned company in Radom providing precise and complex CNC machining services, including CNC milling, CNC turning and wire EDM, manufactured in accordance with ISO 9001:2015 certified by TÜV Rheinland.",
    website: "https://www.cncalfa.pl",
    certifications: ["ISO 9001:2015"],
    sourceUrl: "https://www.cncalfa.pl/en/quality", sourceName: "cncalfa.pl (company site)" },
  { name: "Vistal Gdynia S.A.", country: "PL", city: "Gdynia", yearFounded: 1991, category: STEEL,
    description: "Producer of steel structures active on the European market since 1991, with more than 25 years of experience building steel bridges and structures for the civil, energy, shipbuilding and offshore industries; manufacturing, assembly, corrosion protection and NDT testing facilities.",
    certifications: ["PN-EN 1090-1:2012 (EXC4)", "PN-EN ISO 3834-2"],
    sourceUrl: "https://www.environmental-expert.com/companies/vistal-gdynia-sa-60578", sourceName: "Environmental Expert (directory)" },
  { name: "ZMK WOSTAL Sp. z o.o.", country: "PL", city: "Wolbrom", category: WELD,
    description: "Mechanical and forging works in Wolbrom with nearly 100 years of history, producing steel and aluminium die forgings, welded steel structures, CNC machined parts and laser, plasma and oxygen cutting, with over 200 employees across three production departments.",
    website: "https://wostal.pl",
    certifications: ["DIN EN ISO 3834-2", "EN 17460"],
    awards: ["Diamenty Forbesa 2026"],
    sourceUrl: "https://wostal.pl/", sourceName: "wostal.pl (company site)" },
  { name: "Stal Impex Sp. z o.o.", country: "PL", city: "Krosno", yearFounded: 1997, category: WELD,
    description: "Manufacturer of welded steel tubes, closed profiles and angles since 1997, headquartered in Krosno with a tube production plant in Gorlice and five technological production lines; pipe processing services include laser tube cutting, CNC tube bending and welding.",
    website: "https://www.stalimpex.eu",
    awards: ["Gazele Biznesu", "Gepardy Biznesu", "Diamenty Forbesa"],
    sourceUrl: "https://www.stalimpex.eu/us/about-us/", sourceName: "stalimpex.eu (company site)" },
];

/** Later-sourced public facts for already-imported profiles (see importer) */
const ENRICHMENTS: CatalogEnrichment[] = [
  // Lithuania
  { name: "Westa Steel UAB", city: "Mažeikiai", yearFounded: 2014,
    sourceUrl: "https://www.westasteel.lt/en/about-us/", sourceName: "westasteel.lt (company site)" },
  { name: "Rokvelas UAB", certifications: ["ISO 9001", "EN 1090-1", "EN 1090-2 EXC3"], city: "Panevėžys", yearFounded: 2004, website: "https://rokvelas.lt",
    sourceUrl: "https://www.europages.co.uk/ROKVELAS-UAB/00000003657703-000020534001.html", sourceName: "Europages profile" },
  { name: "Lavango Engineering LT UAB", city: "Klaipėda",
    sourceUrl: "https://www.dnb.com/business-directory/company-profiles.lavango_engineering_lt_uab.decee450438ba0b4431977a9e2f5836f.html", sourceName: "Dun & Bradstreet profile" },
  { name: "Anvalda UAB", city: "Vilnius", website: "https://www.anvalda.com",
    sourceUrl: "https://www.anvalda.com/", sourceName: "anvalda.com (company site)" },
  { name: "GRR Engineering UAB", city: "Utena", yearFounded: 2010, website: "https://www.grr.lt",
    sourceUrl: "https://www.info.lt/en/imones/GRR-Engineering-UAB/2296135", sourceName: "Info.lt company profile" },
  { name: "Stansefabrikken Automotive UAB", certifications: ["ISO 9001:2015", "ISO 14001:2015", "ISO 45001:2018"], city: "Ukmergė", website: "https://www.stansefabrikken.com/StansefabrikkenAutomotive/",
    sourceUrl: "https://www.stansefabrikken.com/StansefabrikkenUkmerge/quality/", sourceName: "Stansefabrikken quality page" },
  { name: "Martema UAB", certifications: ["ISO 9001:2015"], city: "Marijampolė", website: "https://www.martema.lt",
    sourceUrl: "https://www.martema.lt/en/", sourceName: "martema.lt (company site)" },
  { name: "OSS UAB", certifications: ["ISO 9001", "ISO 14001", "ISO 45001", "ISO 3834-2", "EN ISO 9606-1:2013 (welder qualifications)"],
    sourceUrl: "https://www.oss.lt/quality", sourceName: "oss.lt quality page" },
  { name: "Feliuga UAB", certifications: ["ISO 9001", "EN 1090-1+A1"], city: "Klaipėda", website: "https://feliuga.lt",
    sourceUrl: "https://feliuga.lt/quality/", sourceName: "feliuga.lt quality page" },
  { name: "Western Baltija Shipbuilding UAB", yearFounded: 2010,
    sourceUrl: "https://wbs.lt/en/history/", sourceName: "wbs.lt (company site)" },
  { name: "Marine Technology (Western Shipyard Group)", certifications: ["ISO 9001", "ISO 14001", "ISO 45001", "EN 1090 EXC4", "EN 13445"], website: "https://marinetechnology.lt",
    sourceUrl: "https://lt.linkedin.com/company/mtechnology", sourceName: "LinkedIn company page" },
  // Latvia
  { name: "Ritausmas Steel Constructions SIA", certifications: ["EN 1090", "EN 3834"],
    sourceUrl: "https://ritausmas.lv/en/", sourceName: "ritausmas.lv (company site)" },
  { name: "Industrial Welding SIA", certifications: ["DIN EN 1090", "DIN EN ISO 3834", "EN 15085"], city: "Daugavpils", yearFounded: 2016,
    sourceUrl: "https://www.techpilot.com/en/profiles/sia-industrial-welding", sourceName: "Techpilot supplier profile" },
  { name: "EMJ Metals SIA", certifications: ["ISO 9001", "ISO 14001", "ISO 50001", "AQAP"], yearFounded: 2010,
    sourceUrl: "https://www.bmeopensourcing.com/en/supplier-profile/10634/emj-metals-sia", sourceName: "BME OpenSourcing supplier profile" },
  { name: "Metal Constructions (metals.lv)", certifications: ["EN 1090"],
    sourceUrl: "https://metals.lv/en/steel-metal-constructions/metalworking/", sourceName: "metals.lv (company site)" },
  { name: "CNC Latvia Ltd", certifications: ["ISO 9001:2015"],
    sourceUrl: "https://cnclatvia.com/", sourceName: "cnclatvia.com (company site)" },
  { name: "Metalmeistars Ltd", city: "Liepāja",
    sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  { name: "AB Metal Ltd", city: "Liepāja",
    sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  // Estonia
  { name: "AGMA OÜ", certifications: ["EN ISO 3834-2", "EN 1090-1 EXC3"], website: "http://agma.ee/en/",
    sourceUrl: "https://www.europages.co.uk/AGMA/00000003878045-298430001.html", sourceName: "Europages listing" },
  { name: "Monik OÜ", certifications: ["EN 1090-2 EXC4", "EN ISO 3834-2", "ISO 9001:2015", "ISO 14001:2015"],
    sourceUrl: "https://www.monik.ee/", sourceName: "monik.ee (company site)" },
  { name: "Bernal Estonia OÜ", city: "Tallinn", yearFounded: 2010,
    sourceUrl: "https://bernal.ee/en/", sourceName: "bernal.ee (company site)" },
  { name: "Steel Element OÜ", certifications: ["EN 1090-2 EXC3", "ISO 3834-2:2021", "ISO 9001:2015"],
    sourceUrl: "https://steelelement.ee/en/", sourceName: "steelelement.ee (company site)" },
  { name: "Metalset OÜ", city: "Tallinn",
    sourceUrl: "https://flagma.com.ee/en/1963997/", sourceName: "Flagma company listing" },
  { name: "Levstal Group", certifications: ["ISO 9001:2015", "EN 1090-2 EXC3", "EN ISO 3834-2", "PED 2014/68/EU (Annex I, 3.1)"], yearFounded: 1991,
    sourceUrl: "https://levstal.com/", sourceName: "levstal.com (company site)" },
  { name: "Scanweld AS", certifications: ["EN 3834-2", "EN 1090-1 EXC2"], yearFounded: 1991,
    sourceUrl: "https://www.scanweld.ee/about-us/company/certificates/", sourceName: "scanweld.ee certificates page" },
  { name: "Radius Machining OÜ", certifications: ["ISO 9001:2015", "ISO 14001:2015"], website: "https://www.radius.ee",
    sourceUrl: "https://www.radius.ee/en/about-us/quality-and-environment", sourceName: "radius.ee (company site)" },
];

async function main() {
  const admin = await db.query.users.findFirst({
    where: eq(users.email, "admin@balticbridge.example"),
  });
  if (!admin) throw new Error("Run npm run db:seed first");

  let created = 0;
  for (const entry of CATALOG) {
    const existing = await db.query.companies.findFirst({
      where: eq(companies.name, entry.name),
    });
    if (existing) continue;

    await db.transaction(async (tx) => {
      const [company] = await tx
        .insert(companies)
        .values({
          name: entry.name,
          country: entry.country,
          city: entry.city,
          description: entry.description,
          website: entry.website,
          yearFounded: entry.yearFounded,
          category: entry.category,
          claimStatus: "unclaimed",
          sourceUrl: entry.sourceUrl,
          sourceName: entry.sourceName,
          languages: [],
          certifications: entry.certifications ?? [],
          awards: entry.awards ?? [],
        })
        .returning();
      if (!company) throw new Error("insert failed");

      await tx.insert(companySlugs).values({
        companyId: company.id,
        slug: slugify(entry.name, entry.country),
      });
      await writeAudit(tx, {
        actorId: admin.id,
        entityType: "company",
        entityId: company.id,
        action: "company.imported_from_open_source",
        after: { sourceUrl: entry.sourceUrl, sourceName: entry.sourceName },
      });
      await appendOutbox(tx, "companies.imported", { companyId: company.id });
    });
    created += 1;
  }

  // Enrichment: apply later-sourced facts to already-imported profiles.
  // Only fills fields, never downgrades claim status or touches ownership.
  let enriched = 0;
  for (const patch of ENRICHMENTS) {
    const existing = await db.query.companies.findFirst({
      where: eq(companies.name, patch.name),
    });
    if (!existing) continue;

    const set: Record<string, unknown> = {};
    if (patch.certifications?.length) set.certifications = patch.certifications;
    if (patch.awards?.length) set.awards = patch.awards;
    if (patch.city && !existing.city) set.city = patch.city;
    if (patch.yearFounded && !existing.yearFounded) set.yearFounded = patch.yearFounded;
    if (patch.website && !existing.website) set.website = patch.website;
    if (Object.keys(set).length === 0) continue;

    await db.transaction(async (tx) => {
      await tx
        .update(companies)
        .set({ ...set, updatedAt: new Date() })
        .where(eq(companies.id, existing.id));
      await writeAudit(tx, {
        actorId: admin.id,
        entityType: "company",
        entityId: existing.id,
        action: "company.enriched_from_open_source",
        before: {
          certifications: existing.certifications,
          awards: existing.awards,
        },
        after: { ...set, sourceUrl: patch.sourceUrl, sourceName: patch.sourceName },
      });
    });
    enriched += 1;
  }

  logger.info(
    `catalog seed complete: ${created} new unclaimed profiles (${CATALOG.length} total in catalog), ${enriched} enriched`,
  );
  await pool.end();
}

main().catch((error) => {
  logger.error(error, "catalog seed failed");
  process.exit(1);
});
