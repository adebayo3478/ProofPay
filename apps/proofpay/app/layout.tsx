import "./globals.css";
import Providers from "./providers";

export const metadata = {
  title: "ProofPay",
  description: "Invoice + USDT0 checkout"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="container">
            <div className="card hero">
              <h2>ProofPay</h2>
              <div className="muted">USDT0 checkout</div>
            </div>
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
