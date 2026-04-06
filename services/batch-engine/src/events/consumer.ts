/**
 * SQS Event Consumer — listens for order events from order-svc.
 *
 * Events consumed:
 *   - order.confirmed → add order to batch pool
 *   - order.cancelled → remove from pool or batch
 *
 * In production, this runs as a long-polling loop.
 * In dev, it uses LocalStack SQS.
 */

import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from "@aws-sdk/client-sqs";
import { AWS_CONFIG } from "../config";
import { BatchService } from "../services/batch.service";
import { logger } from "../utils/logger";

const sqs = new SQSClient({
  region: AWS_CONFIG.region,
  ...(AWS_CONFIG.endpoint ? { endpoint: AWS_CONFIG.endpoint } : {}),
});

const batchService = new BatchService();

/**
 * Start the SQS consumer loop.
 * Polls for messages and routes them to the appropriate handler.
 */
export async function startConsumer(): Promise<void> {
  if (!AWS_CONFIG.sqsOrderEventsUrl) {
    logger.warn("SQS_QUEUE_URL_BATCH not configured — event consumer disabled");
    return;
  }

  logger.info("Starting SQS event consumer", {
    queueUrl: AWS_CONFIG.sqsOrderEventsUrl,
  });

  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const response = await sqs.send(
        new ReceiveMessageCommand({
          QueueUrl: AWS_CONFIG.sqsOrderEventsUrl,
          MaxNumberOfMessages: 10,
          WaitTimeSeconds: 20,
          VisibilityTimeout: 60,
        })
      );

      if (!response.Messages || response.Messages.length === 0) continue;

      for (const message of response.Messages) {
        try {
          await handleMessage(message.Body ?? "{}");
          // Delete message on success
          await sqs.send(
            new DeleteMessageCommand({
              QueueUrl: AWS_CONFIG.sqsOrderEventsUrl,
              ReceiptHandle: message.ReceiptHandle!,
            })
          );
        } catch (err) {
          logger.error("Failed to process SQS message", {
            error: err instanceof Error ? err.message : String(err),
            messageId: message.MessageId,
          });
          // Message will return to queue after visibility timeout
        }
      }
    } catch (err) {
      logger.error("SQS poll error", {
        error: err instanceof Error ? err.message : String(err),
      });
      // Wait before retrying to avoid tight error loops
      await new Promise((r) => setTimeout(r, 5000));
    }
  }
}

async function handleMessage(body: string): Promise<void> {
  // SNS wraps the actual message in a "Message" field
  const envelope = JSON.parse(body);
  const payload = envelope.Message ? JSON.parse(envelope.Message) : envelope;
  const eventType: string = payload.type ?? payload.eventType ?? "";

  logger.debug("Processing event", { eventType, orderId: payload.orderId });

  switch (eventType) {
    case "order.confirmed":
      await batchService.addToPool({
        orderId: payload.orderId,
        restaurantId: payload.restaurantId,
        restaurantName: payload.restaurantName ?? "Unknown",
        pickupPoint: payload.pickupPoint,
        deliveryPoint: payload.deliveryPoint,
        prepReadyAt: payload.prepReadyAt,
        promisedDeliveryAt: payload.promisedDeliveryAt,
        priority: payload.priority ?? "standard",
        itemCount: payload.itemCount ?? 1,
        estimatedSizeLiters: payload.estimatedSizeLiters ?? 5,
        currency: payload.currency ?? "USD",
        deliveryFee: payload.deliveryFee ?? 0,
      });
      break;

    case "order.cancelled":
      // Try to remove from pool first, then from batch
      if (payload.batchId) {
        await batchService.removeOrderFromBatch(
          payload.batchId,
          payload.orderId,
          "customer_cancelled"
        );
      }
      break;

    default:
      logger.debug("Ignoring unhandled event type", { eventType });
  }
}
