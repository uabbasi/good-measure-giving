export interface PlanItem {
  id: string;                       // client-generated uuid, stable
  kind: 'charity' | 'category';
  ref: string;                      // EIN (charity) or category slug
  weight: number;                   // proportion / relative weight (NOT dollars)
  assigneeUid: string | null;       // member covering this item, or null
  updatedAt: number;                // epoch ms
  updatedBy: string;                // uid
  notes?: Record<string, { text: string; at: number }>; // per-member niyyah, keyed by uid
}

export interface ShortlistCandidate {
  ref: string;        // EIN of a charity being considered (not yet committed)
  addedBy: string;    // uid
  addedAt: number;    // epoch ms
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
  shortlist?: ShortlistCandidate[];
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
