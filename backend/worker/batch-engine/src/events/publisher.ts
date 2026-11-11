/**
 * SNS Event Publisher — publishes batch events to SNS.
 *
 * Events published:
 *   - batch.formed     → new batch created, ready for driver assignment
 *   - batch.assigned   → driver accepted the batch
 *   - batch.completed  → all deliveries done
 *   - batch.failed     → batch couldn't be completed
 *   - batch.order_removed → order removed mid-delivery
 */

import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";
import { AWS_CONFIG } from "../config";
import { BatchEvent } from "../types";
import { logger } from "../utils/logger";

const sns = new SNSClient({
  region: AWS_CONFIG.region,
  ...(AWS_CONFIG.endpoint ? { endpoint: AWS_CONFIG.endpoint } : {}),
});

/**
 * Publish a batch event to SNS.
 * Fails silently in development if SNS is not configured.
 */
export async function publishBatchEvent(event: BatchEvent): Promise<void> {
  if (!AWS_CONFIG.snsTopicArn) {
    logger.debug("SNS not configured — skipping event publish", {
      eventType: event.type,
    });
    return;
  }

  try {
    await sns.send(
      new PublishCommand({
        TopicArn: AWS_CONFIG.snsTopicArn,
        Message: JSON.stringify(event),
        MessageAttributes: {
          eventType: {
            DataType: "String",
            StringValue: event.type,
          },
        },
      })
    );

    logger.debug("Published batch event", {
      type: event.type,
      batchId: event.batchId,
    });
  } catch (err) {
    logger.error("Failed to publish batch event", {
      type: event.type,
      batchId: event.batchId,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}
