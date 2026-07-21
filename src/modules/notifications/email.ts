import { env } from "@/lib/env";
import { logger } from "@/lib/logger";

/**
 * Single EmailProvider interface (Section 3). Amazon SES (eu-north-1) is the
 * first real adapter; the console adapter is used in development and tests.
 */
export interface EmailMessage {
  to: string;
  subject: string;
  text: string;
  html?: string;
}

export interface EmailProvider {
  send(message: EmailMessage): Promise<void>;
}

class ConsoleEmailProvider implements EmailProvider {
  async send(message: EmailMessage): Promise<void> {
    logger.info(
      { to: message.to, subject: message.subject, body: message.text },
      "email (console provider)",
    );
  }
}

class SesEmailProvider implements EmailProvider {
  async send(message: EmailMessage): Promise<void> {
    // Lazy import keeps the SDK out of the dev/test path.
    const { SESv2Client, SendEmailCommand } = await import(
      "@aws-sdk/client-sesv2"
    );
    const client = new SESv2Client({ region: env.S3_REGION });
    await client.send(
      new SendEmailCommand({
        FromEmailAddress: env.EMAIL_FROM,
        Destination: { ToAddresses: [message.to] },
        Content: {
          Simple: {
            Subject: { Data: message.subject },
            Body: {
              Text: { Data: message.text },
              ...(message.html ? { Html: { Data: message.html } } : {}),
            },
          },
        },
      }),
    );
  }
}

export function emailProvider(): EmailProvider {
  return env.EMAIL_PROVIDER === "ses"
    ? new SesEmailProvider()
    : new ConsoleEmailProvider();
}
