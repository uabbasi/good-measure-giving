export interface DevTestUser {
  id: 'fresh' | 'active-donor';
  label: string;
  email: string;
  password: string;
  displayName: string;
  seed: boolean;
}

export const DEV_TEST_USERS: DevTestUser[] = [
  { id: 'fresh',        label: 'Fresh User',   email: 'fresh@test.local', password: 'test1234', displayName: 'Fresh User',   seed: false },
  { id: 'active-donor', label: 'Active Donor', email: 'donor@test.local', password: 'test1234', displayName: 'Active Donor', seed: true },
];
