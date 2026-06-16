import type { Database, Order } from "../repositories/orders";
import { getOrder, listOrders } from "../repositories/orders";

export type ActorContext = {
  userId: string;
};

export async function showOpenOrders(db: Database, actor: ActorContext): Promise<Order[]> {
  void actor;
  return listOrders(db, "open");
}

export async function showOrderDetail(db: Database, actor: ActorContext, orderId: string): Promise<Order | null> {
  return getOrder(db, orderId, actor.userId);
}
