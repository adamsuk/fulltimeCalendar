import { useEffect, useState } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell, Center, Loader } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { loadAllData } from './data';
import type { AppData } from './types';
import { SiteHeader } from './components/SiteHeader';
import { SiteSidebar } from './components/SiteSidebar';
import { HomePage } from './pages/HomePage';
import { AboutPage } from './pages/AboutPage';
import { TeamsPage } from './pages/TeamsPage';
import { RegisterPage } from './pages/RegisterPage';
import { CommitteePage } from './pages/CommitteePage';
import { NewsPage } from './pages/NewsPage';
import { GalleryPage } from './pages/GalleryPage';
import { MatchdayPage } from './pages/MatchdayPage';
import { ContactPage } from './pages/ContactPage';
import { FixturesResultsPage } from './pages/FixturesResultsPage';

export default function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [opened, { toggle, close }] = useDisclosure();

  useEffect(() => {
    loadAllData().then(setData);
  }, []);

  if (!data) {
    return (
      <Center h="100vh">
        <Loader color="orange" size="xl" />
      </Center>
    );
  }

  return (
    <HashRouter>
      <AppShell
        header={{ height: 60 }}
        navbar={{ width: 300, breakpoint: 'md', collapsed: { mobile: !opened } }}
        padding="md"
      >
        <AppShell.Header>
          <SiteHeader club={data.club} navOpen={opened} onNavToggle={toggle} />
        </AppShell.Header>

        <AppShell.Navbar>
          <SiteSidebar
            club={data.club}
            fixture={data.fixtures.next}
            bantamsFeed={data.bantamsFeed}
            onNavClick={close}
          />
        </AppShell.Navbar>

        <AppShell.Main>
          <Routes>
            <Route path="/" element={<HomePage club={data.club} />} />
            <Route path="/about" element={<AboutPage club={data.club} />} />
            <Route path="/teams" element={<TeamsPage teams={data.teams} />} />
            <Route path="/fixtures" element={<FixturesResultsPage feed={data.bantamsFeed} />} />
            <Route path="/register" element={<RegisterPage items={data.registration} />} />
            <Route path="/committee" element={<CommitteePage committee={data.committee} teams={data.teams} />} />
            <Route path="/news" element={<NewsPage items={data.news} />} />
            <Route path="/gallery" element={<GalleryPage items={data.gallery} />} />
            <Route path="/matchday" element={<MatchdayPage items={data.matchday} />} />
            <Route path="/contact" element={<ContactPage club={data.club} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </HashRouter>
  );
}
