import { GetObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { randomUUID } from "node:crypto";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { requireAnyRole, type Actor } from "@/modules/identity/rbac";
import { writeAudit } from "@/modules/audit/service";
import { documents } from "./schema";

export type DocumentRow = typeof documents.$inferSelect;

/** Presigned URLs expire ≤ 15 min (Section 4.7) */
const PRESIGN_TTL_SECONDS = 15 * 60;

function s3(): S3Client {
  return new S3Client({
    region: env.S3_REGION,
    endpoint: env.S3_ENDPOINT,
    forcePathStyle: env.S3_FORCE_PATH_STYLE,
    credentials:
      env.S3_ACCESS_KEY_ID && env.S3_SECRET_ACCESS_KEY
        ? {
            accessKeyId: env.S3_ACCESS_KEY_ID,
            secretAccessKey: env.S3_SECRET_ACCESS_KEY,
          }
        : undefined,
  });
}

/** Register a document and return a presigned PUT URL for the private,
 * versioned documents bucket. */
export async function createUpload(
  actor: Actor,
  input: {
    companyId: string;
    workerId?: string;
    fileName: string;
    contentType: string;
    documentType?: string;
  },
): Promise<{ document: DocumentRow; uploadUrl: string }> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);

  const objectKey = `companies/${input.companyId}/${randomUUID()}/${input.fileName}`;

  const document = await db.transaction(async (tx) => {
    const [row] = await tx
      .insert(documents)
      .values({
        companyId: input.companyId,
        workerId: input.workerId,
        fileName: input.fileName,
        contentType: input.contentType,
        documentType: input.documentType,
        objectKey,
        uploadedBy: actor.userId,
      })
      .returning();
    if (!row) throw new Error("Document insert failed");
    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "document",
      entityId: row.id,
      action: "document.upload_created",
      after: { objectKey, documentType: input.documentType },
    });
    return row;
  });

  const uploadUrl = await getSignedUrl(
    s3(),
    new PutObjectCommand({
      Bucket: env.S3_DOCUMENTS_BUCKET,
      Key: objectKey,
      ContentType: input.contentType,
    }),
    { expiresIn: PRESIGN_TTL_SECONDS },
  );

  return { document, uploadUrl };
}

/** Presigned GET for inline preview in the review queue */
export async function getDownloadUrl(
  actor: Actor,
  documentId: string,
): Promise<string> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);

  const row = await db.query.documents.findFirst({
    where: eq(documents.id, documentId),
  });
  if (!row) throw new Error("Document not found");

  return getSignedUrl(
    s3(),
    new GetObjectCommand({
      Bucket: env.S3_DOCUMENTS_BUCKET,
      Key: row.objectKey,
    }),
    { expiresIn: PRESIGN_TTL_SECONDS },
  );
}

/**
 * Generic presign helpers for other modules' media (e.g. portfolio images).
 * Same bucket, same ≤15 min expiry; callers own their metadata rows.
 */
export async function presignPut(
  keyPrefix: string,
  fileName: string,
  contentType: string,
): Promise<{ objectKey: string; uploadUrl: string }> {
  const objectKey = `${keyPrefix}/${randomUUID()}/${fileName}`;
  const uploadUrl = await getSignedUrl(
    s3(),
    new PutObjectCommand({
      Bucket: env.S3_DOCUMENTS_BUCKET,
      Key: objectKey,
      ContentType: contentType,
    }),
    { expiresIn: PRESIGN_TTL_SECONDS },
  );
  return { objectKey, uploadUrl };
}

export async function presignGet(objectKey: string): Promise<string> {
  return getSignedUrl(
    s3(),
    new GetObjectCommand({ Bucket: env.S3_DOCUMENTS_BUCKET, Key: objectKey }),
    { expiresIn: PRESIGN_TTL_SECONDS },
  );
}

/**
 * Malware scan hook (Section 4.7). GuardDuty Malware Protection for S3 will
 * publish scan results; until enabled this stub marks uploads clean in dev.
 */
export async function markScanResult(
  documentId: string,
  status: "clean" | "infected" | "error",
): Promise<void> {
  await db
    .update(documents)
    .set({ scanStatus: status })
    .where(eq(documents.id, documentId));
}
