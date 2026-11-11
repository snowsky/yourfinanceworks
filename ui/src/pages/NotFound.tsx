import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { BrandMark } from "@/components/auth/BrandMark";
import { ProfessionalButton } from "@/components/ui/professional-button";

const NotFound = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="px-6 pt-6 sm:px-10">
        <BrandMark />
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md text-center">
          <p className="font-mono text-sm font-semibold tracking-widest text-primary">404</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
            {t("notFound.title")}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground text-balance">
            {t("notFound.description")}
          </p>
          <p className="mt-4 inline-block max-w-full truncate rounded-lg border border-border bg-muted/50 px-3 py-1.5 font-mono text-xs text-muted-foreground">
            {location.pathname}
          </p>

          <div className="mt-8 flex flex-col-reverse items-center justify-center gap-3 sm:flex-row">
            <ProfessionalButton
              type="button"
              variant="outline"
              size="lg"
              className="w-full sm:w-auto"
              onClick={() => navigate(-1)}
            >
              <ArrowLeft aria-hidden="true" />
              {t("notFound.back")}
            </ProfessionalButton>
            <ProfessionalButton asChild variant="gradient" size="lg" className="w-full sm:w-auto">
              <Link to="/">{t("notFound.home")}</Link>
            </ProfessionalButton>
          </div>
        </div>
      </main>
    </div>
  );
};

export default NotFound;
