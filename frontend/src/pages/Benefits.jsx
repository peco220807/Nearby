import Eligibility from "../components/Eligibility/Eligibility.jsx";
import Layout from "../components/Layout.jsx";

// The benefits check is not tied to a family and saves nothing
export default function Benefits() {
  return (
    <Layout>
      <Eligibility />
    </Layout>
  );
}
