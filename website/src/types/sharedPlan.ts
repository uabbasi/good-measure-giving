export interface PlanItem {
  id: string;                       // client-generated uuid, stable
  kind: 'charity' | 'category';
  ref: string;                      // EIN (charity) or category slug
  weight: number;                   // proportion / relative weight (NOT dollars)
  assigneeUid: string | null;       // member covering this item, or null
  updatedAt: number;                // epoch ms
  updatedBy: string;                // uid
}

export interface SharedPlan {
  id: string;
  name: string;
  ownerId: string;
  createdAt: number;
  updatedAt: number;
  revision: number;
  inviteToken: string;
  items: PlanItem[];
}

export interface PlanMember {
  uid: string;
  role: 'owner' | 'editor';
  displayName: string;
  joinedAt: number;
}

export interface PlanHistoryEntry {
  revision: number;
  itemId: string;
  before: PlanItem | null;
  after: PlanItem | null;
  updatedBy: string;
  at: number;
}
