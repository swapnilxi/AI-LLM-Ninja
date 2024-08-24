
import Head from 'next/head';
import Tabs from './components/Tabs';

export default function Home() {
  return (
    <div>
      <Head>
        <title>Next.js Tabs Example</title>
      </Head>
      <main>
        <h1></h1>
        <Tabs />
      </main>
    </div>
  );
}
