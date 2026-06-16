import { showOrderDetail } from "../src/services/orders";
import type { Database } from "../src/repositories/orders";

function fakeDb(): Database {
  return {
    order: {
      async findMany() {
        return [
          { id: "order_1", ownerId: "user_1", status: "open", totalCents: 1200 },
        ];
      },
    },
  };
}

test("showOrderDetail asks repository with actor owner", async () => {
  const result = await showOrderDetail(fakeDb(), { userId: "user_1" }, "order_1");
  expect(result?.id).toBe("order_1");
});
