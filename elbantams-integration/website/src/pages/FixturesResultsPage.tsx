import { useState, useMemo } from 'react';
import {
  Title, Text, Stack, Paper, Badge, Group, Select, Tabs,
  Table, Alert,
} from '@mantine/core';
import { IconCalendar, IconTrophy, IconAlertCircle } from '@tabler/icons-react';
import type { BantamsFeed } from '../types';

interface Props {
  feed: BantamsFeed | null;
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

export function FixturesResultsPage({ feed }: Props) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);

  const teamNames = useMemo(() => {
    if (!feed) return [];
    const names = new Set<string>();
    feed.fixtures.forEach((f) => names.add(f.team));
    feed.results.forEach((r) => names.add(r.team));
    return Array.from(names).sort();
  }, [feed]);

  const fixtures = useMemo(() => {
    if (!feed) return [];
    const list = selectedTeam
      ? feed.fixtures.filter((f) => f.team === selectedTeam)
      : feed.fixtures;
    return [...list].sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));
  }, [feed, selectedTeam]);

  const results = useMemo(() => {
    if (!feed) return [];
    const list = selectedTeam
      ? feed.results.filter((r) => r.team === selectedTeam)
      : feed.results;
    return [...list].sort((a, b) => b.date.localeCompare(a.date) || b.time.localeCompare(a.time));
  }, [feed, selectedTeam]);

  if (!feed) {
    return (
      <Stack gap="md">
        <Title order={2}>Fixtures & Results</Title>
        <Alert icon={<IconAlertCircle size={16} />} color="orange">
          Live fixture and result data is currently unavailable. Please check back later.
        </Alert>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Title order={2}>Fixtures & Results</Title>

      <Text size="sm" c="dimmed">
        Data sourced from FA Full-Time via{' '}
        <Text component="a" href="https://github.com/adamsuk/fulltimeCalendar" c="orange.6" size="sm">
          fulltimeCalendar
        </Text>
        . Last updated: {new Date(feed.generated).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}.
      </Text>

      <Select
        label="Filter by team"
        placeholder="All Bantams teams"
        data={teamNames}
        value={selectedTeam}
        onChange={setSelectedTeam}
        clearable
        searchable
      />

      <Tabs defaultValue="fixtures" color="orange">
        <Tabs.List>
          <Tabs.Tab value="fixtures" leftSection={<IconCalendar size={14} />}>
            Fixtures ({fixtures.length})
          </Tabs.Tab>
          <Tabs.Tab value="results" leftSection={<IconTrophy size={14} />}>
            Results ({results.length})
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="fixtures" pt="md">
          {fixtures.length === 0 ? (
            <Text c="dimmed" size="sm">No upcoming fixtures.</Text>
          ) : (
            <Stack gap="xs">
              {fixtures.map((f) => (
                <Paper key={f.id} p="sm" withBorder radius="md">
                  <Group justify="space-between" wrap="wrap" gap="xs" mb={4}>
                    <Badge color="orange" variant="light" size="xs">{f.division}</Badge>
                    <Text size="xs" c="dimmed">{formatDate(f.date)} · {f.time}</Text>
                  </Group>
                  <Text fw={700} size="sm" ta="center">
                    {f.home_team} vs {f.away_team}
                  </Text>
                  <Text size="xs" c="dimmed" ta="center">{f.venue}</Text>
                </Paper>
              ))}
            </Stack>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="results" pt="md">
          {results.length === 0 ? (
            <Text c="dimmed" size="sm">No results yet.</Text>
          ) : (
            <Table striped highlightOnHover withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Date</Table.Th>
                  <Table.Th>Home</Table.Th>
                  <Table.Th ta="center">Score</Table.Th>
                  <Table.Th>Away</Table.Th>
                  <Table.Th visibleFrom="sm">Division</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {results.map((r) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Text size="xs">{formatDate(r.date)}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={r.home_away === 'home' ? 700 : 400}>
                        {r.home_team}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="center">
                      <Text size="sm" fw={700}>
                        {r.home_score ?? 'X'} - {r.away_score ?? 'X'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={r.home_away === 'away' ? 700 : 400}>
                        {r.away_team}
                      </Text>
                    </Table.Td>
                    <Table.Td visibleFrom="sm">
                      <Text size="xs" c="dimmed">{r.division}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
