import { Footer } from "./Footer";
import { Navbar } from "./Navbar";
import { SkipLink } from "./SkipLink";

type SiteLayoutProps = {
  children: React.ReactNode;
  cartCount?: number;
};

export function SiteLayout({ children, cartCount }: SiteLayoutProps) {
  return (
    <>
      <SkipLink />
      <Navbar cartCount={cartCount} />
      {children}
      <Footer />
    </>
  );
}
