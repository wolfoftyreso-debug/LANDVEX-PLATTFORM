import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { listCorridors } from "@/modules/catalog/service";
import {
  getCompany,
  listContacts,
  listWorkers,
} from "@/modules/companies/service";
import { documents } from "@/modules/documents/schema";
import { verificationCases } from "@/modules/verification/schema";
import { badgeVisible, type CaseState } from "@/modules/verification/domain";
import {
  addContactAction,
  addWorkerAction,
  openCaseAction,
} from "@/app/[locale]/admin/actions";

export const dynamic = "force-dynamic";

/** Company 360° view: profile, workers, documents, verification history */
export default async function CompanyDetail({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("companies");
  const tVerification = await getTranslations("verification");
  const tState = await getTranslations("caseState");

  const company = await getCompany(id);
  if (!company) notFound();

  const [workers, contacts, docs, cases, corridors] = await Promise.all([
    listWorkers(id),
    listContacts(id),
    db.select().from(documents).where(and(eq(documents.companyId, id))),
    db.select().from(verificationCases).where(eq(verificationCases.companyId, id)),
    listCorridors(),
  ]);

  const kase = cases[0];
  const state = kase?.state as CaseState | undefined;

  return (
    <div>
      <h1>{company.name}</h1>
      <p className="muted">
        {company.country}
        {company.city ? ` · ${company.city}` : ""}
        {company.registrationNumber ? ` · ${t("registrationNumber")}: ${company.registrationNumber}` : ""}
        {company.vatNumber ? ` · ${t("vatNumber")}: ${company.vatNumber}` : ""}
      </p>

      {/* Verification */}
      <div className="card">
        <h3>{t("verificationCase")}</h3>
        {kase && state ? (
          <p>
            <span className={`badge ${state}`}>{tState(state)}</span>{" "}
            {badgeVisible(state) && (
              <span className="badge verified">
                ✓ {tVerification("verifiedBadge")}
              </span>
            )}{" "}
            <Link href={`/${locale}/admin/verification/${kase.id}`}>→</Link>
          </p>
        ) : (
          <div>
            <p className="muted">{t("noCase")}</p>
            <form action={openCaseAction} className="inline">
              <input type="hidden" name="companyId" value={company.id} />
              <input
                type="hidden"
                name="corridorId"
                value={corridors[0]?.id ?? ""}
              />
              {workers.map((w) => (
                <input key={w.id} type="hidden" name="workerIds" value={w.id} />
              ))}
              <button type="submit" disabled={!corridors[0]}>
                {tVerification("openCase")} ({corridors[0]?.slug ?? "—"})
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Workers */}
      <div className="card">
        <h3>{t("workers")}</h3>
        {workers.length > 0 && (
          <table>
            <tbody>
              {workers.map((w) => (
                <tr key={w.id}>
                  <td>{w.name}</td>
                  <td className="muted">{w.tradeRole ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form action={addWorkerAction} className="inline mt">
          <input type="hidden" name="companyId" value={company.id} />
          <div>
            <label htmlFor="worker-name">{t("workerName")}</label>
            <input id="worker-name" name="name" required />
          </div>
          <div>
            <label htmlFor="worker-role">{t("tradeRole")}</label>
            <input id="worker-role" name="tradeRole" placeholder="welder" />
          </div>
          <button type="submit">{t("addWorker")}</button>
        </form>
      </div>

      {/* Contacts */}
      <div className="card">
        <h3>{t("contacts")}</h3>
        {contacts.length > 0 && (
          <table>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td className="muted">{c.email ?? "—"}</td>
                  <td className="muted">{c.phone ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form action={addContactAction} className="inline mt">
          <input type="hidden" name="companyId" value={company.id} />
          <div>
            <label htmlFor="contact-name">{t("workerName")}</label>
            <input id="contact-name" name="name" required />
          </div>
          <div>
            <label htmlFor="contact-email">Email</label>
            <input id="contact-email" name="email" type="email" />
          </div>
          <div>
            <label htmlFor="contact-phone">Tel</label>
            <input id="contact-phone" name="phone" />
          </div>
          <button type="submit" className="secondary">+</button>
        </form>
      </div>

      {/* Documents */}
      <div className="card">
        <h3>{t("documents")}</h3>
        {docs.length === 0 ? (
          <p className="muted">—</p>
        ) : (
          <table>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>{d.fileName}</td>
                  <td className="muted">{d.documentType ?? "—"}</td>
                  <td>
                    <span className={`badge ${d.scanStatus === "clean" ? "approved" : ""}`}>
                      {d.scanStatus}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
