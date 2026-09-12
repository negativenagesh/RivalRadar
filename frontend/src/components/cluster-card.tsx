"use client";

import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Cluster } from "@/lib/types";

function formatLabel(format: string) {
  return format.replace(/_/g, " ");
}

export function ClusterCard({ cluster, index }: { cluster: Cluster; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: "easeOut" }}
      whileHover={{ y: -3 }}
    >
      <Card className="h-full border-border/60 bg-card/60 transition-colors hover:border-primary/50">
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <Badge variant="secondary" className="mb-2 capitalize">
              {formatLabel(cluster.format)}
            </Badge>
            <p className="text-sm text-muted-foreground">{cluster.dominant_theme}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold tabular-nums text-primary">
              {cluster.total_engagement.toLocaleString()}
            </p>
            <p className="text-xs text-muted-foreground">total engagement</p>
          </div>
        </CardHeader>
        <CardContent>
          <p className="line-clamp-3 text-sm text-foreground/90">
            &ldquo;{cluster.top_post_caption}&rdquo;
          </p>
          <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
            <span>{cluster.post_count} posts</span>
            <span>{cluster.account_ids.length} accounts</span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
