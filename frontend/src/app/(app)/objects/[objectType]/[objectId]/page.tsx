import { FeaturePlaceholder } from "@/components/shared/feature-placeholder";

type ObjectPageProps = {
  params: Promise<{
    objectType: string;
    objectId: string;
  }>;
};

export default async function ObjectDetailPage({ params }: ObjectPageProps) {
  const resolved = await params;

  return (
    <FeaturePlaceholder
      title={`${resolved.objectType} object placeholder`}
      description={`This route reserves the future object-detail experience for ${resolved.objectId}, including linked evidence, permitted functions, actions, and audit context.`}
    />
  );
}
