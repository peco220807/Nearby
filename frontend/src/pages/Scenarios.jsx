import Scenarios from "../components/Scenarios/Scenarios.jsx";
import Layout from "../components/Layout.jsx";

// The calculator is not tied to a family and saves nothing
export default function ScenariosPage() {
  return (
    <Layout wide>
      <Scenarios />
    </Layout>
  );
}
