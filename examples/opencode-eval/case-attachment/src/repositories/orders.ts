export type Order = {
  id: string;
  ownerId: string;
  status: "open" | "closed";
  totalCents: number;
};

export type Database = {
  order: {
    findMany: (query: unknown) => Promise<Order[]>;
  };
};

export async function listOrders(db: Database, status: Order["status"]): Promise<Order[]> {
  return db.order.findMany({
    where: {
      status,
    },
    orderBy: {
      id: "asc",
    },
  });
}

export async function getOrder(db: Database, orderId: string, ownerId: string): Promise<Order | null> {
  const rows = await db.order.findMany({
    where: {
      id: orderId,
      ownerId,
    },
  });
  return rows[0] ?? null;
}
